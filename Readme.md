# Install
    pip3 uninstall ccxt -y
    pip3 install ccxt --no-compile --no-cache-dir --force-reinstall
    install
    python3 -m venv .venv
    python3 install poetry

# Poetry
    poetry install
    poetry add ...
    poetry run ...


# Crypto Discord Bot

Bot Discord kết nối với sàn giao dịch cryptocurrency thông qua CCXT library.

## Tính năng

- 🚀 **Trending**: Hiển thị các đồng tiền giao dịch nổi bật
- 💰 **Price Check**: Kiểm tra giá realtime của các đồng tiền
- 📊 **Market Analysis**: Phân tích và nhận xét về thị trường
- 🔄 **Interactive**: Buttons và dropdown để cập nhật thông tin

## Cài đặt

1. Clone repository
2. Cài đặt Poetry: `pip install poetry`
3. Cài đặt dependencies: `poetry install`
4. Tạo file `.env` với các thông tin cần thiết
5. Chạy bot: `poetry run python -m app.main`

## Cấu hình

Tạo file `.env`:


# pyenv:
    pyenv install [version]
    # Kiểm tra Python version hiện tại
# hoặc
    python --version
    pyenv version

# Kiểm tra đường dẫn Python
    which python

# Set Python 3.12 cho project này
    pyenv local 3.14.0

# Kiểm tra
    python --version  # Nên show Python 3.12.0

# Tạo mới project với Python 3.12
    poetry env use 3.12.0

# Hoặc chỉ định đường dẫn cụ thể
    poetry env use ~/.pyenv/versions/3.12.0/bin/python

# Kiểm tra environment
    poetry env info