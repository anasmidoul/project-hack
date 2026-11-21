"""Start the HOUSIA web app on config.PORT."""

from housia import config, create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=config.PORT)
