# Install poetry
    python3 install poetry

# Add dependencies
    poetry add [dependencies]

# ReInstall
    poetry lock
    poetry install
# Run 
    poetry run python -m app.main
# Run watch
    node istall -g nodemon
    poetry run nodemon --exec "python -m app.main" --ext py --watch app