# kf

# Flask Application Setup (Windows)

This guide explains how to set up and run a Flask application on **Windows**, including creating a virtual environment, installing dependencies, and running the app.


##  Setup Instructions

### 1. Clone the Project (or download ZIP)
```bash
git clone git@github.com:asingo-paul/kf.git
cd kf
````

---

### 2. Create a Virtual Environment

```bash
python -m venv .venv
```

This will create a folder called `venv` in your project.

---

### 3. Activate the Virtual Environment

```bash
.venv\Scripts\activate
```

Once activated, your terminal should show `(venv)` before the path.

To **deactivate**:

```bash
deactivate
```

### 4. Install Dependencies

install the dependancies

```bash
pip install -r requirements.txt
```
the requirements file is already present use it

### 6. Run the Flask App

```bash
python app.py
```

Or if your app uses Flask CLI:

```bash
flask run
```

By default, the app runs on:

```
http://127.0.0.1:5000/
```

---

##  Troubleshooting

* If `flask` command is not recognized, install it:

  ```bash
  pip install flask
  ```
* Make sure the virtual environment is activated before installing/running.
* If using MySQL, ensure MySQL server is running.

You’re all set! Your Flask app should now run on Windows.

## To bypass running scripts of windows

## Open powershel as an administrator and run this command
   
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
