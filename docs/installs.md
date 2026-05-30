# Install poetry 3.12
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

## Deploy Ubuntu 20.04/Focal

Ubuntu 20.04 có thể không cài được `python3.12` bằng `apt`, kể cả khi đã thêm `deadsnakes`.
Trong trường hợp đó, cài Python bằng `pyenv` trước rồi mới cài Poetry.

### Cài dependencies để build Python

```bash
sudo apt update
sudo apt install -y \
  build-essential curl git make \
  libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev \
  libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev \
  libffi-dev liblzma-dev
```

### Cài pyenv

```bash
curl https://pyenv.run | bash
```

Thêm `pyenv` vào shell:

```bash
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
source ~/.bashrc
```

### Cài Python 3.12.13

```bash
pyenv install 3.12.13
pyenv global 3.12.13
python --version
```

Kết quả cần là:

```bash
Python 3.12.13
```

### Cài Poetry

Poetry cần Python đúng version trước khi chạy `poetry install`.

```bash
curl -sSL https://install.python-poetry.org | python -
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
poetry --version
```

### Cài dependency project

```bash
cd xda_tradding
python -m venv .venv
source .venv/bin/activate
pip install -U pip
poetry install
```

### Chạy bot

```bash
poetry run python -m app.main
```

### Chạy watch khi dev

```bash
npm install -g nodemon
poetry run nodemon --exec "python -m app.main" --ext py --watch app
```

### Lưu ý

- Không commit file `.env`.
- Nếu `poetry install` báo sai Python version, kiểm tra lại `python --version` và chạy `poetry env use python`.
- Thứ tự đúng là cài Python 3.12.13 trước, sau đó mới cài Poetry và dependency.
