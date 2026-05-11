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

This client can use the Naco API. To generate client based on Naco's openapi spec, make sure `openapi.json` is available
at `../naco/openapi.json` and run `python tools/generate_client.py` to replace all files in `naco-backend-client`. Then
run `uv pip install -e ./naco-backend-client` to update the local `.venv` with the new client files.
