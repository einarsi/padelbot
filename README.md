# PadelBot

Bot for Equinor BIL Padel group for interaction with Spond

## Configuration

The bot requires Spond credentials for a user that does not have 2FA enabled.

### Environment variables

| Variable         | Description    | Required |
| ---------------- | -------------- | -------- |
| `SPOND_USERNAME` | Spond username | Yes      |
| `SPOND_PASSWORD` | Spond password | Yes      |
| `SPOND_GROUP_ID` | Spond group ID | Yes      |

### Local development

Create a `.env` file in the project root:

```dotenv
SPOND_USERNAME=your_username
SPOND_PASSWORD=your_password
SPOND_GROUP_ID=your_group_id
```

From the top directory, execute `python src/webapp.py`.

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
listed in `ALLOWED_PATHS` in `tools/generate_client.py` are included. To update it after a change in Naco:

1. Make the new spec available at `../naco/openapi.json`.
2. Regenerate the client. This replaces all files in `naco-backend-client/`:

   ```sh
   uv run python tools/generate_client.py
   ```

3. Reinstall the client into the local `.venv`. The bot and the tests import the installed copy, not the folder:

   ```sh
   uv sync --reinstall-package naco-backend-client
   ```

4. Run the tests. `tests/padelbot/naco/test_wire.py` fails if the requests the bot sends, or the responses it can
   parse, have changed:

   ```sh
   uv run pytest
   ```

5. Commit `naco-backend-client/` together with `uv.lock`.
