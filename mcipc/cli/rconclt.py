"""RCON client CLI."""

from argparse import ArgumentParser, Namespace
from getpass import getpass
from logging import DEBUG, INFO, basicConfig, getLogger
from socket import timeout
from subprocess import CalledProcessError, check_call
from sys import exit    # pylint: disable=W0622
from typing import Tuple

from mcipc.constants import ERR_CONNECTION_REFUSED
from mcipc.constants import ERR_CONNECTION_TIMEOUT
from mcipc.constants import ERR_NO_SUCH_SERVER
from mcipc.constants import ERR_REQUEST_ID_MISMATCH
from mcipc.constants import ERR_USER_ABORT
from mcipc.constants import ERR_WRONG_PASSWORD
from mcipc.constants import LOG_FORMAT
from mcipc.enumerations import Edition
from mcipc.exceptions import InvalidConfig
from mcipc.rcon import CLIENTS
from mcipc.rcon.config import Config, servers
from mcipc.rcon.exceptions import RequestIdMismatch, WrongPassword
from mcipc.rcon.proto import Client
from mcipc.rcon.response_types import Players


__all__ = ['get_credentials', 'main']


LOGGER = getLogger('rconclt')


def get_args() -> Namespace:
    """Parses and returns the CLI arguments."""

    parser = ArgumentParser(description='A Minecraft RCON client.')
    parser.add_argument('server', help='the server to connect to')
    parser.add_argument(
        '-t', '--timeout', type=float, metavar='seconds',
        help='connection timeout in seconds')
    parser.add_argument(
        '-d', '--debug', action='store_true',
        help='print additional debug information')
    subparsers = parser.add_subparsers(dest='action')
    command_parser = subparsers.add_parser(
        'exec', help='execute commands on the server')
    command_parser.add_argument(
        'command', help='command to execute on the server')
    command_parser.add_argument(
        'argument', nargs='*', default=(), help='arguments for the command')
    say_parser = subparsers.add_parser(
        'say', help='broadcast a message on the server')
    say_parser.add_argument('message', help='the message to broadcast')
    fortune_parser = subparsers.add_parser(
        'fortune', help='send a fortune to the players on the server')
    fortune_parser.add_argument(
        '-l', '--long', action='store_true', help='generate ling fortunes')
    fortune_parser.add_argument(
        '-o', '--offensive', action='store_true',
        help='generate offensive fortunes')
    datetime_parser = subparsers.add_parser(
        'datetime',
        help='sends the current date and time to the players on the server')
    datetime_parser.add_argument(
        '-f', '--format', default='%c', metavar='format_string',
        help='the datetime format')
    subparsers.add_parser('in-use', help='checks whether the server is in use')
    shutdown_parser = subparsers.add_parser(
        'idle-shutdown', help='shuts down the server if it is not in use')
    shutdown_parser.add_argument(
        '-s', '--sudo', action='store_true',
        help='invoke the shutdown command using sudo')
    shutdown_parser.add_argument(
        '-u', '--unit', default='minecraft@{server}.service', metavar='unit',
        help='the systemd unit template')
    return parser.parse_args()


def get_credentials(server: str) -> Tuple[Edition, str, int, str]:
    """Get the credentials for a server from the respective server name."""

    try:
        edition, host, port, passwd = Config.from_string(server)
    except InvalidConfig:
        try:
            edition, host, port, passwd = servers()[server]
        except KeyError:
            LOGGER.error('No such server: %s.', server)
            exit(ERR_NO_SUCH_SERVER)

    if passwd is None:
        try:
            passwd = getpass('Password: ')
        except (KeyboardInterrupt, EOFError):
            print()
            LOGGER.error('Aborted by user.')
            exit(ERR_USER_ABORT)

    return (edition, host, port, passwd)


def idle_shutdown(players: Players, args: Namespace) -> bool:
    """Shuts down the server if it is idle."""

    if players.online:
        LOGGER.info('Server is in use.')
        return False

    LOGGER.info('Server is idle.')
    unit = args.unit.format(server=args.server)
    command = ('/usr/bin/systemctl', 'stop', unit)

    try:
        check_call(command)
    except CalledProcessError as error:
        LOGGER.error('Could not shutdown the server.')
        LOGGER.debug(error)
        return False

    LOGGER.info('Server %s has been shut down.', unit)
    return True


def run_action(client: Client, args: Namespace):
    """Runs the respective actions."""

    result = None

    if args.action == 'exec':
        result = client.run(args.command, *args.argument)
    elif args.action == 'say':
        result = client.say(args.message)
    elif args.action == 'fortune':
        result = client.fortune(
            short=not args.long, offensive=args.offensive)
    elif args.action == 'datetime':
        result = client.datetime(frmt=args.format)
    elif args.action == 'in-use':
        players = client.players

        if players.online:
            LOGGER.info('There are %i players online:', players.online)
            LOGGER.info(', '.join(players.names))
        else:
            LOGGER.warning('There are no players online.')
            exit(1)

    if result:
        LOGGER.info(result)


def main():
    """Runs the RCON client."""

    args = get_args()
    log_level = DEBUG if args.debug else INFO
    basicConfig(level=log_level, format=LOG_FORMAT)
    edition, host, port, passwd = get_credentials(args.server)

    try:
        with CLIENTS[edition](host, port, timeout=args.timeout) as client:
            client.login(passwd)

            if args.action == 'idle-shutdown':
                if not idle_shutdown(client.players, args):
                    exit(1)
            else:
                run_action(client, args)
    except ConnectionRefusedError:
        LOGGER.error('Connection refused.')
        exit(ERR_CONNECTION_REFUSED)
    except timeout:
        LOGGER.error('Connection timeout.')
        exit(ERR_CONNECTION_TIMEOUT)
    except RequestIdMismatch:
        LOGGER.error('Unexpected request ID mismatch.')
        exit(ERR_REQUEST_ID_MISMATCH)
    except WrongPassword:
        LOGGER.error('Wrong password.')
        exit(ERR_WRONG_PASSWORD)
