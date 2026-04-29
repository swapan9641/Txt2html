FROM python:3.10-slim-buster

WORKDIR /app
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port for cloud platforms
EXPOSE ${PORT:-8080}

# Run the bot
CMD ["python3", "bot.py"]
