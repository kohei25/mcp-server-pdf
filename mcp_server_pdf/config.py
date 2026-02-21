import sys

from loguru import logger

# stdoutはMCPのstdio通信で使うため、loguruの出力はstderrのみにする
logger.remove()
logger.add(sys.stderr, level="INFO")
