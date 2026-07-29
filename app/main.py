import time

from .config import load_config
from .database_client import DatabaseClient, DatabaseError
from .email_manager import EmailManager
from .ia_client import IAClient
from .logger import Logger
from .parser import Parser

def main() -> None:
  config = load_config()
  email_manager = EmailManager(config.imap, config.smtp, config.processed_folder, config.failed_folder)
  parser = Parser(IAClient(config.api_key))
  database_client = DatabaseClient(config.database)
  logger = Logger()

  while True:
    try:
      mails = email_manager.fetch()
      processed_emails = parser.parse_all(mails)
    except Exception as error:
      logger.log_error(str(error))
      time.sleep(config.interval_minutes)
      continue
  
    for processed_email in processed_emails:
      if processed_email.error:
        handle_error(processed_email.error, processed_email.email, email_manager, logger)
        continue
      try:
        database_client.add(processed_email.data)
        email_manager.mark_completed(processed_email.email)
        email_manager.reply_success(processed_email.email, processed_email.data)
      except Exception as error:
        handle_error(str(error), processed_email.email, email_manager, logger)

    time.sleep(config.interval_minutes)

def handle_error(error: str, email, email_manager: EmailManager, logger: Logger):
  logger.log_error(error)
  email_manager.mark_failed(email)
  email_manager.reply_failed(email, error)