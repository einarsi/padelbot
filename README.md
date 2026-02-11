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

```
SPOND_USERNAME=your_username
SPOND_PASSWORD=your_password
SPOND_GROUP_ID=your_group_id
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
