# PadelBot

Bot for Equinor BIL Padel group for interaction with Spond

## Configuration

The bot requires Spond credentials for a user that does not have 2FA enabled.

### Environment variables

| Variable                      | Description                           | Required |
| ----------------------------- | ------------------------------------- | -------- |
| `SPOND_USERNAME`              | Spond username                        | Yes      |
| `SPOND_PASSWORD`              | Spond password                        | Yes      |
| `SPOND_GROUP_ID`              | Spond group ID                        | Yes      |
| `SPOND_INCLUDE_HIDDEN_EVENTS` | Fetch invitee-only events (see below) | No       |

By default the bot also fetches events that only invitees can see when its own Spond account is not one of them. Set
`SPOND_INCLUDE_HIDDEN_EVENTS` to `false` to leave them out, or to `true`, `1` or `yes` to include them.

Each `SPOND_<KEY>` variable overrides `<key>` under `[spond]` in `config.toml`.

### Local development

Create a `.env` file in the project root:

```dotenv
SPOND_USERNAME=your_username
SPOND_PASSWORD=your_password
SPOND_GROUP_ID=your_group_id
```

From the top directory, execute `python src/webapp.py`.

### Tests

```sh
uv run pytest
```

This runs everything except the live checks, and needs no credentials or network.

Before a deploy, the live checks confirm that the bot can still talk to the real Spond and Naco. They use the
configuration the bot uses (`config.toml`, `.env` and environment variables) and only read:

```sh
uv run pytest -m live
```

## Docker

### Build

```sh
docker build -t padelbot .
```

### Run

```sh
docker run -d \
  -e SPOND_USERNAME=your_username \
  -e SPOND_PASSWORD=your_password \
  -e SPOND_GROUP_ID=your_group_id \
  -p 8000:8000 \
  padelbot
```

The web interface is available at `http://localhost:8000`.

The container healthcheck uses `/health`, which answers 200 only when the bot has completed a cycle and the next one
is not more than two minutes overdue. It answers 503 when credentials are missing or the bot loop keeps failing. A
cycle in which Spond could not be reached still counts as completed.

## Naco integration

When enabled, the bot registers event participants as users in Naco and creates tournaments for events that match a
`NacoCreateTournament` action in `config.toml`.

| Variable        | Description                            | Required        |
| --------------- | -------------------------------------- | --------------- |
| `NACO_ENABLED`  | `true`, `1` or `yes` to enable Naco    | No              |
| `NACO_BASE_URL` | Base URL of the Naco backend           | If Naco enabled |
| `NACO_API_KEY`  | API key sent in the `x-api-key` header | If Naco enabled |

The same settings can be given in the `[naco]` section of `config.toml`; environment variables take precedence.

### Updating the Naco client

The bot talks to Naco through a client in `naco-backend-client/`, generated from Naco's OpenAPI spec. Only the endpoints
listed in `ALLOWED_PATHS` in `tools/generate_client.py` are included. The client is installed in editable mode, so the
bot and the tests import it straight from that folder. To update it after a change in Naco:

1. Make the new spec available at `../naco/openapi.json`.
2. Regenerate the client. This replaces all files in `naco-backend-client/` and updates `uv.lock`:

   ```sh
   uv run python tools/generate_client.py
   ```

3. Run the tests. `tests/padelbot/naco/test_wire.py` fails if the requests the bot sends, or the responses it can
   parse, have changed. `uv run` also installs any new dependencies of the client:

   ```sh
   uv run pytest
   ```

4. Commit `naco-backend-client/` together with `uv.lock`.

The Docker image installs a regular copy of the client instead (`--no-editable` in the `Dockerfile`).
