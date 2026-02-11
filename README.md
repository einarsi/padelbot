# PadelBot

Bot for Equinor BIL Padel group for interaction with Spond

## Configuration

The bot requires Spond credentials for a user that does not have 2FA enabled.

### Environment variables

| Variable   | Description    | Required |
| ---------- | -------------- | -------- |
| `USERNAME` | Spond username | Yes      |
| `PASSWORD` | Spond password | Yes      |
| `GROUP_ID` | Spond group ID | Yes      |

### Local development

Create a `.env` file in the project root:

```
USERNAME=your_username
PASSWORD=your_password
GROUP_ID=your_group_id
```

## Docker

### Build

```sh
docker build -t padelbot .
```

### Run

```sh
docker run -d \
  -e USERNAME=your_username \
  -e PASSWORD=your_password \
  -e GROUP_ID=your_group_id \
  -p 8000:8000 \
  padelbot
```

The web interface is available at `http://localhost:8000`.
