import asyncio
import logging
from datetime import datetime, timedelta

from spond import spond

from .actions.actionbase import ActionBase, ActionIntent, create_action
from .actions.naco_create_tournament import CreateTournamentIntent
from .naco.registrar import NacoRegistrar
from .naco.tournament import NacoTournamentCreator
from .rules.rulebase import RuleBase, create_rule
from .utils import Event, Events, eventid_to_event, memberid_to_member


class PadelBot:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        try:
            self.spond = spond.Spond(cfg["auth"]["username"], cfg["auth"]["password"])
        except Exception as e:
            logging.error(f"Failed to initialize Spond client: {e}")
            raise
        self.naco_enabled = cfg["naco"].get("enabled", False)
        if self.naco_enabled:
            self.naco_registrar = NacoRegistrar(
                base_url=cfg["naco"]["base_url"],
                api_key=cfg["naco"].get("api_key", ""),
            )
            self.naco_tournament_creator = NacoTournamentCreator(
                base_url=cfg["naco"]["base_url"],
                api_key=cfg["naco"].get("api_key", ""),
            )
        self.first_run = True
        self.spond_profile_id: str | None = None
        self.events = Events()  # Cache events for webapp access

    async def resolve_spond_profile_id(self) -> None:
        """Fetch the connected user's Spond profile ID on first run."""
        if self.spond_profile_id:
            return
        try:
            profile = await self.spond.get_profile()
            self.spond_profile_id = profile.get("id")
            if self.spond_profile_id:
                logging.info(f"Resolved my Spond profile ID: {self.spond_profile_id}")
            else:
                logging.error(
                    "Spond profile response did not contain an 'id' field. "
                    "Tournament creation will be disabled."
                )
        except Exception as e:
            logging.error(
                f"Failed to fetch Spond profile: {e}. "
                f"Tournament creation will be disabled until resolved."
            )

    async def get_events(self) -> Events:
        timestamp_now = datetime.now().astimezone()
        min_start = timestamp_now - timedelta(days=7)
        try:
            events = (
                await self.spond.get_events(
                    group_id=self.cfg["auth"]["group_id"],
                    min_start=min_start,
                    max_start=None,
                )
                or []
            )
        except Exception as e:
            logging.error(f"Failed to fetch events from Spond: {e}")
            return Events()

        timestamp_now = datetime.now().astimezone()
        retval = Events()
        for event in events:
            startTimestamp = datetime.fromisoformat(event["startTimestamp"])
            endTimestamp = datetime.fromisoformat(event["endTimestamp"])
            if startTimestamp > datetime.now().astimezone():
                retval.upcoming.append(event)
            elif endTimestamp < datetime.now().astimezone():
                retval.previous.append(event)
            else:
                retval.ongoing.append(event)

        logging.debug(
            f"Found {len(retval.upcoming)} upcoming, {len(retval.previous)} previous and {len(retval.ongoing)} ongoing events"
        )
        return retval

    def get_rules(self, events: Events) -> list[RuleBase]:
        rules = []
        for rule_name, rule_def in self.cfg["rules"].items():
            try:
                rule = create_rule(rule_name, events, rule_def)
            except ValueError as e:
                logging.error(f"Skipping rule {rule_name}: {e}")
                continue
            rules.append(rule)
        return rules

    def get_actions(self, events: Events) -> list[ActionBase]:
        actions: list[ActionBase] = []
        if not self.spond_profile_id:
            if self.cfg["actions"]:
                logging.error(
                    "Cannot create actions: Spond profile ID not resolved. "
                    "Check connectivity to Spond."
                )
            return actions
        for action_name, action_def in self.cfg["actions"].items():
            action_def = {**action_def, "spond_profile_id": self.spond_profile_id}
            try:
                action = create_action(action_name, events, action_def)
            except ValueError as e:
                logging.error(f"Skipping action {action_name}: {e}")
                continue
            actions.append(action)
        return actions

    async def execute_action(self, intent: ActionIntent) -> bool:
        if isinstance(intent, CreateTournamentIntent):
            if not self.naco_enabled:
                logging.warning(
                    f'Cannot create tournament for "{intent.event_heading}": Naco is disabled'
                )
                return False
            return await self.naco_tournament_creator.create_tournament(
                event_id=intent.event_id,
                event_heading=intent.event_heading,
                tournament_name=intent.tournament_name,
                tournament_type=intent.tournament_type,
                created_by_spond_id=intent.created_by_spond_id,
                player_spond_ids=intent.player_spond_ids,
                start_time=intent.start_time,
                points_to_win=intent.points_to_win,
                court_names=intent.court_names,
            )
        logging.error(f"Unknown action intent type: {type(intent).__name__}")
        return False

    def get_sleep_time(self, default_sleep_time: float, events: Events) -> float:
        # Identify next rule/quarantine end time. Must be in the future.
        seconds_to_sleep = default_sleep_time

        all_rule_end_times = [
            dt for rule in self.get_rules(events) for dt in rule.expirationtimes()
        ]
        now = datetime.now().astimezone()
        next_rule_end_time = min(
            (dt for dt in all_rule_end_times if dt > now), default=None
        )
        if next_rule_end_time:
            secs_to_quarantine_end = (next_rule_end_time - now).total_seconds()
            logging.debug(
                f"Next quarantine ends at {next_rule_end_time.astimezone().replace(tzinfo=None)} (in {secs_to_quarantine_end:.2f} seconds)"
            )

            if (
                1 < secs_to_quarantine_end <= 60
            ):  # Aim for 1 second before, every 20 secs until then
                seconds_to_sleep = max(1, min(20, secs_to_quarantine_end - 1))
            else:  # Aim for 59 seconds before to enter interval above
                seconds_to_sleep = max(
                    1,
                    min(
                        default_sleep_time,
                        secs_to_quarantine_end - 59,
                    ),
                )

        # Cap sleep so we don't miss an action window
        next_action_time = min(
            (
                dt
                for action in self.get_actions(events)
                for dt in action.expirationtimes()
                if dt > now
            ),
            default=None,
        )
        if next_action_time:
            secs_to_action = (next_action_time - now).total_seconds()
            seconds_to_sleep = min(seconds_to_sleep, secs_to_action)

        return seconds_to_sleep

    def update_events_with_removal(
        self, player_id: str, event_id: str, events: Events
    ) -> Events:
        updated_events = []
        for event in events.upcoming:
            if event["id"] == event_id:
                # Remove player_id from whichever group they are in
                for key in ("waitinglistIds", "acceptedIds"):
                    if player_id in event["responses"][key]:
                        event["responses"][key].remove(player_id)
                        break  # Player can only be in one group, so stop after removal
            updated_events.append(event)
        events.upcoming = updated_events
        return events

    async def remove_player_from_event(
        self,
        player_id: str,
        event_id: str,
        message: str,
        events: list[Event],
        enforce: bool = False,
    ) -> bool:
        try:
            event = eventid_to_event(event_id, events)
        except ValueError:
            logging.error(f"Event ID {event_id} not found")
            return False

        player = memberid_to_member(
            player_id,
            event["recipients"]["group"]["members"],
        )

        logging.info(
            f'{"Removing" if enforce else "Not enforcing removal of"} player {player["firstName"]} {player["lastName"]} from event "{event["heading"]}" ({event["startTimestamp"]})'
        )
        if enforce:
            try:
                await self.spond.change_response(
                    event_id, player_id, {"accepted": "false"}
                )
                await self.spond.send_message(
                    text=message,
                    user=player["id"],
                    group_uid=self.cfg["auth"]["group_id"],
                )
                return True
            except Exception as e:
                logging.error(
                    f'Failed to remove player {player["firstName"]} {player["lastName"]} from event "{event["heading"]}": {e}'
                )
                return False
        return False

    async def run(self):
        await self.resolve_spond_profile_id()
        events = await self.get_events()
        self.events = events  # Cache events for webapp access

        if self.naco_enabled:
            await self.naco_registrar.register_event_users(
                events.upcoming, self.spond.get_person
            )

        all_removals = []
        for rule in self.get_rules(events):
            removals = rule.evaluate()
            for removal in removals:
                # Update events so that subsequent rules see the to-be-updated state
                if removal.enforced:
                    events = self.update_events_with_removal(
                        removal.player_id, removal.event_id, events
                    )
            all_removals.extend(removals)

        for removal in all_removals:
            await self.remove_player_from_event(
                player_id=removal.player_id,
                event_id=removal.event_id,
                message=removal.message,
                events=events.upcoming,
                enforce=removal.enforced and not self.first_run,
            )

        # Evaluate and execute actions
        if not self.first_run:
            all_intents = []
            for action in self.get_actions(events):
                intents = action.evaluate()
                all_intents.extend(intents)

            for intent in all_intents:
                if intent.enforced:
                    await self.execute_action(intent)

        self.first_run = False

        seconds_to_sleep = self.get_sleep_time(
            self.cfg["general"]["seconds_to_sleep"], events
        )

        logging.info(f"Sleeping for {seconds_to_sleep:.1f} seconds")
        await asyncio.sleep(seconds_to_sleep)
