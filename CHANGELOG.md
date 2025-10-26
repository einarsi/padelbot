# Changelog

## [1.1.3](https://github.com/einarsi/padelbot/compare/v1.1.2...v1.1.3) (2025-10-26)


### 🐛 Bug Fixes

* daylight savings offset for quarantine rule ([#22](https://github.com/einarsi/padelbot/issues/22)) ([f1bde27](https://github.com/einarsi/padelbot/commit/f1bde27cb1434585b5b5d450613d85ee7cfe43f8))


### 🧪 Tests

* add tests for rules ([#15](https://github.com/einarsi/padelbot/issues/15)) ([e31939b](https://github.com/einarsi/padelbot/commit/e31939b005c780ce5c046736c0b43fa0c852fe1c))

## [1.1.2](https://github.com/einarsi/padelbot/compare/v1.1.1...v1.1.2) (2025-10-22)


### 🐛 Bug Fixes

* time offset error in previous quarantine fix ([#20](https://github.com/einarsi/padelbot/issues/20)) ([4a5e581](https://github.com/einarsi/padelbot/commit/4a5e581cf56c753403fba8f9302f053304b881cf))

## [1.1.1](https://github.com/einarsi/padelbot/compare/v1.1.0...v1.1.1) (2025-10-22)


### 🐛 Bug Fixes

* one day quarantine lasts for 25 hours ([#19](https://github.com/einarsi/padelbot/issues/19)) ([18a19af](https://github.com/einarsi/padelbot/commit/18a19af24159ea1595f57bd0961f80882bc78b4c))


### 🧹 Chores

* **deps:** bump aiofiles from 24.1.0 to 25.1.0 ([#12](https://github.com/einarsi/padelbot/issues/12)) ([fdb1a03](https://github.com/einarsi/padelbot/commit/fdb1a03d5be994316f5ab88cf558a6872d83a786))
* **deps:** bump ruff from 0.13.3 to 0.14.1 ([#16](https://github.com/einarsi/padelbot/issues/16)) ([ec9c57a](https://github.com/einarsi/padelbot/commit/ec9c57a509a1b7de04d6e005784cdbd84bb8dd30))
* **deps:** bump uvicorn from 0.37.0 to 0.38.0 ([#17](https://github.com/einarsi/padelbot/issues/17)) ([61c8b23](https://github.com/einarsi/padelbot/commit/61c8b2372e7e155a394cc97c9727b6f9ed3ff8b1))


### 👷 CI/CD

* add PR name validator ([5f82b99](https://github.com/einarsi/padelbot/commit/5f82b99e623a97cb8c07e94adaf3db9170ebb94f))


### 🧪 Tests

* add tests for padelbot.py and utils.py ([#8](https://github.com/einarsi/padelbot/issues/8)) ([9c4e924](https://github.com/einarsi/padelbot/commit/9c4e9240464b4c5a792567a0f0289e1770645f51))

## [1.1.0](https://github.com/einarsi/padelbot/compare/v1.0.7...v1.1.0) (2025-10-05)


### ✨ Features

* do not remove players on first run ([9e90535](https://github.com/einarsi/padelbot/commit/9e90535077500515e005731404c0d57a94b2e0a5))
* filter events on header for rule application ([6c2f93d](https://github.com/einarsi/padelbot/commit/6c2f93d06b98a89a7fa07e5fedc48bad89d19c15))


### 🧹 Chores

* **deps:** bump ruff from 0.13.0 to 0.13.2 ([#2](https://github.com/einarsi/padelbot/issues/2)) ([ac40735](https://github.com/einarsi/padelbot/commit/ac40735f85dabb96b3554ca69e836a0753f5afea))

## [1.0.7](https://github.com/einarsi/padelbot/compare/v1.0.6...v1.0.7) (2025-10-01)


### 🐛 Bug Fixes

* do not expire quarantine if no previous event ([78a05bf](https://github.com/einarsi/padelbot/commit/78a05bf62e181499d2c73a2411f23f318c0a0b67))


### 👷 CI/CD

* do not push attestations to docker hub ([dacaa62](https://github.com/einarsi/padelbot/commit/dacaa6214239c31e594746c391b17d7cfbaef0c2))


### 🧪 Tests

* add first set of tests ([c78e918](https://github.com/einarsi/padelbot/commit/c78e91837894ef496a5aa240bf90189b3594f4b1))

## [1.0.6](https://github.com/einarsi/padelbot/compare/v1.0.5...v1.0.6) (2025-09-30)


### 👷 CI/CD

* push to docker also on push main (revert test) ([dc63b8c](https://github.com/einarsi/padelbot/commit/dc63b8c0b675fdff2f0afc3ad98d04b0714be66e))
* use PAT for release-please ([0e7f470](https://github.com/einarsi/padelbot/commit/0e7f470795073f971b059a839f51335a977ae3bf))

## [1.0.5](https://github.com/einarsi/padelbot/compare/v1.0.4...v1.0.5) (2025-09-30)


### 👷 CI/CD

* only push to docker hub on tag push (test) ([58149c5](https://github.com/einarsi/padelbot/commit/58149c509e54129f34b74409840037bb033ed163))

## [1.0.4](https://github.com/einarsi/padelbot/compare/v1.0.3...v1.0.4) (2025-09-30)


### 👷 CI/CD

* add dependabot.yml ([ec94cfb](https://github.com/einarsi/padelbot/commit/ec94cfb85ea41aa85c06b01d08f7c2595839fb0e))
* add release please ([9d13434](https://github.com/einarsi/padelbot/commit/9d1343417086fb4827ce545b2d0ce269079810b5))
* push to dockerhub on push to main and tags ([5fe3d71](https://github.com/einarsi/padelbot/commit/5fe3d71834d208d1fdc9a92561257b78686c70c2))
