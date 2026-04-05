# SmartWaste Management System

This project now uses a real SQLite database instead of browser-side static demo data.

It includes:
- role-based login
- SQLite-backed CRUD for users, bins, tasks, alerts, and AI validation history
- generated reports for users, bins, tasks, and validation runs with date filters and export options
- admin ability to create city heads and staff accounts
- trained waste-level model for `low`, `medium`, `high`
- ultrasonic sensor comparison against the AI result

## Main files

- [app.py](C:/Users/Noman/Desktop/db/app.py)
- [database.py](C:/Users/Noman/Desktop/db/database.py)
- [config.py](C:/Users/Noman/Desktop/db/config.py)
- [train_model.py](C:/Users/Noman/Desktop/db/train_model.py)
- [predict_cli.py](C:/Users/Noman/Desktop/db/predict_cli.py)
- [main.py](C:/Users/Noman/Desktop/db/main.py)

## Database

SQLite database file:

- [smartwaste.db](C:/Users/Noman/Desktop/db/smartwaste.db)

Tables created automatically:

- `users`
- `bins`
- `tasks`
- `alerts`
- `validation_runs`

## Default login

When the database is empty, the app creates one admin account automatically:

- Username: `admin`
- Password: `admin123`

After login, the admin can create:

- `city_head` users
- `staff` users

## CRUD included

Admin:
- create, read, update, delete users
- create, read, update, delete bins
- create, read, update, delete tasks
- create, read, update, delete alerts
- create, read, update, delete validation history
- generate filtered exports for users, bins, tasks, and validation runs

City Head:
- create, read, update, delete bins
- create, read, update, delete tasks
- create, read, update, delete alerts
- read and review AI validations
- generate filtered exports for users, bins, tasks, and validation runs

Staff:
- read assigned bins
- read assigned tasks
- update own task status
- read alerts and update alert status
- update own profile

## Dataset and model

Your trained model artifacts are here:

- [waste_level_model.keras](C:/Users/Noman/Desktop/db/saved_models/waste_level_model.keras)
- [training_summary.json](C:/Users/Noman/Desktop/db/saved_models/training_summary.json)
- [training_curves.png](C:/Users/Noman/Desktop/db/saved_models/training_curves.png)

Latest trained test accuracy:

- `86.16%`

## Install packages

```powershell
pip install -r requirements.txt
```

## Train the model

```powershell
python train_model.py
```

## Run the app

```powershell
python app.py
```

Open:

- [http://127.0.0.1:5000](http://127.0.0.1:5000)

## Sensor modes

Default mode is:

- `auto`

That means the app tries the serial ultrasonic sensor first and still supports manual/HTTP input.

Examples:

Manual:
```powershell
set SENSOR_MODE=manual
python app.py
```

Serial:
```powershell
set SENSOR_MODE=serial
set SERIAL_PORT=COM6
set BAUD_RATE=115200
python app.py
```

HTTP sensor:
```powershell
set SENSOR_MODE=http
set SENSOR_API_KEY=my_ultrasonic_token
python app.py
```

## ESP8266 / NodeMCU

Use [main.py](C:/Users/Noman/Desktop/db/main.py) on the microcontroller side.

Update:
- `FLASK_SERVER_IP`
- `FLASK_SERVER_PORT`
- `API_PATH`
- `API_TOKEN`

## Validation flow

1. Login as admin or city head
2. Open `AI Validation`
3. Select a bin or enter a location
4. Use live sensor reading or type manual sensor distance
5. Upload the dustbin image
6. Run validation
7. Review the saved validation record from SQLite

## Notes

- `main.py` is MicroPython code for ESP8266 / NodeMCU, not desktop Python.
- The old static demo data file has been removed.
- The frontend now reads live data from Flask APIs only.
