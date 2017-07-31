# This file is part of JujuPy, a library for driving the Juju CLI.
# Copyright 2014-2017 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the Lesser GNU General Public License version 3, as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.  See the Lesser
# GNU General Public License for more details.
#
# You should have received a copy of the Lesser GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from contextlib import contextmanager
from datetime import (
    datetime,
    )
import errno
import glob
import os
import re
from shutil import rmtree
import subprocess
import socket
import sys
from time import (
    sleep,
    )
from tempfile import (
    mkdtemp,
    NamedTemporaryFile,
    )
# Export shell quoting function which has moved in newer python versions
try:
    from shlex import quote
except ImportError:
    from pipes import quote
import yaml

quote

# Equivalent of socket.EAI_NODATA when using windows sockets
# <https://msdn.microsoft.com/ms740668#WSANO_DATA>
WSANO_DATA = 11004

lxc_template_glob = '/var/lib/juju/containers/juju-*-lxc-template/*.log'


class until_timeout:

    """Yields remaining number of seconds.  Stops when timeout is reached.

    :ivar timeout: Number of seconds to wait.
    """
    def __init__(self, timeout, start=None):
        self.timeout = timeout
        if start is None:
            start = self.now()
        self.start = start

    def __iter__(self):
        return self

    @staticmethod
    def now():
        return datetime.now()

    def __next__(self):
        return self.next()

    def next(self):
        elapsed = self.now() - self.start
        remaining = self.timeout - elapsed.total_seconds()
        if remaining <= 0:
            raise StopIteration
        return remaining


class JujuResourceTimeout(Exception):
    """A timeout exception for a resource not being downloaded into a unit."""


def pause(seconds):
    print_now('Sleeping for {:d} seconds.'.format(seconds))
    sleep(seconds)


def is_ipv6_address(address):
    """Returns True if address is IPv6 rather than IPv4 or a host name.

    Incorrectly returns False for IPv6 addresses on windows due to lack of
    support for socket.inet_pton there.
    """
    try:
        socket.inet_pton(socket.AF_INET6, address)
    except (AttributeError, socket.error):
        # IPv4 or hostname
        return False
    return True


def split_address_port(address_port):
    """Split an ipv4 or ipv6 address and port into a tuple.

    ipv6 addresses must be in the literal form with a port ([::12af]:80).
    ipv4 addresses may be without a port, which translates to None.
    """
    if ':' not in address_port:
        # This is correct for ipv4.
        return address_port, None
    address, port = address_port.rsplit(':', 1)
    address = address.strip('[]')
    return address, port


def print_now(string):
    print(string)
    sys.stdout.flush()


@contextmanager
def temp_dir(parent=None, keep=False):
    directory = mkdtemp(dir=parent)
    try:
        yield directory
    finally:
        if not keep:
            rmtree(directory)


def check_free_disk_space(path, required, purpose):
    df_result = subprocess.check_output(["df", "-k", path])
    df_result = df_result.split('\n')[1]
    df_result = re.split(' +', df_result)
    available = int(df_result[3])
    if available < required:
        message = (
            "Warning: Probably not enough disk space available for\n"
            "%(purpose)s in directory %(path)s,\n"
            "mount point %(mount)s\n"
            "required: %(required)skB, available: %(available)skB."
            )
        print(message % {
            'path': path, 'mount': df_result[5], 'required': required,
            'available': available, 'purpose': purpose
            })


@contextmanager
def skip_on_missing_file():
    """Skip to the end of block if a missing file exception is raised."""
    try:
        yield
    except (IOError, OSError) as e:
        if e.errno != errno.ENOENT:
            raise


def ensure_dir(path):
    try:
        os.mkdir(path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def ensure_deleted(path):
    with skip_on_missing_file():
        os.unlink(path)


@contextmanager
def temp_yaml_file(yaml_dict, encoding="utf-8"):
    temp_file_cxt = NamedTemporaryFile(suffix='.yaml', delete=False)
    try:
        with temp_file_cxt as temp_file:
            yaml.safe_dump(yaml_dict, temp_file, encoding=encoding)
        yield temp_file.name
    finally:
        os.unlink(temp_file.name)


def get_timeout_path():
    import jujupy.timeout
    return os.path.abspath(jujupy.timeout.__file__)


def copy_remote_logs(remote, directory):
    """Copy as many logs from the remote host as possible to the directory."""
    # This list of names must be in the order of creation to ensure they
    # are retrieved.
    if remote.is_windows():
        log_paths = [
            "%ProgramFiles(x86)%\\Cloudbase Solutions\\Cloudbase-Init\\log\\*",
            "C:\\Juju\\log\\juju\\*.log",
        ]
    else:
        log_paths = [
            '/var/log/cloud-init*.log',
            '/var/log/juju/*.log',
            # TODO(gz): Also capture kvm container logs?
            '/var/lib/juju/containers/juju-*-lxc-*/',
            '/var/log/lxd/juju-*',
            '/var/log/lxd/lxd.log',
            '/var/log/syslog',
            '/var/log/mongodb/mongodb.log',
            '/etc/network/interfaces',
            '/etc/environment',
            '/home/ubuntu/ifconfig.log',
        ]

        try:
            wait_for_port(remote.address, 22, timeout=60)
        except PortTimeoutError:
            logging.warning("Could not dump logs because port 22 was closed.")
            return

        try:
            remote.run('sudo chmod -Rf go+r ' + ' '.join(log_paths))
        except subprocess.CalledProcessError as e:
            # The juju log dir is not created until after cloud-init succeeds.
            logging.warning("Could not allow access to the juju logs:")
            logging.warning(e.output)
        try:
            remote.run('ifconfig > /home/ubuntu/ifconfig.log')
        except subprocess.CalledProcessError as e:
            logging.warning("Could not capture ifconfig state:")
            logging.warning(e.output)

    try:
        remote.copy(directory, log_paths)
    except (subprocess.CalledProcessError,
            winrm.exceptions.WinRMTransportError) as e:
        # The juju logs will not exist if cloud-init failed.
        logging.warning("Could not retrieve some or all logs:")
        if getattr(e, 'output', None):
            logging.warning(e.output)
        else:
            logging.warning(repr(e))


def copy_local_logs(env, directory):
    """Copy logs for all machines in local environment."""
    local = get_local_root(get_juju_home(), env)
    log_names = [os.path.join(local, 'cloud-init-output.log')]
    log_names.extend(glob.glob(os.path.join(local, 'log', '*.log')))
    log_names.extend(glob.glob(lxc_template_glob))
    try:
        subprocess.check_call(['sudo', 'chmod', 'go+r'] + log_names)
        subprocess.check_call(['cp'] + log_names + [directory])
    except subprocess.CalledProcessError as e:
        logging.warning("Could not retrieve local logs: %s", e)


def archive_logs(log_dir):
    """Compress log files in given log_dir using gzip."""
    log_files = []
    for r, ds, fs in os.walk(log_dir):
        log_files.extend(os.path.join(r, f) for f in fs if is_log(f))
    if log_files:
        subprocess.check_call(['gzip', '--best', '-f'] + log_files)


def is_log(file_name):
    """Check to see if the given file name is the name of a log file."""
    return file_name.endswith('.log') or file_name.endswith('syslog')


def wait_for_port(host, port, closed=False, timeout=30):
    family = socket.AF_INET6 if is_ipv6_address(host) else socket.AF_INET
    for remaining in until_timeout(timeout):
        try:
            addrinfo = socket.getaddrinfo(host, port, family,
                                          socket.SOCK_STREAM)
        except socket.error as e:
            if e.errno not in (socket.EAI_NODATA, WSANO_DATA):
                raise
            if closed:
                return
            else:
                continue
        sockaddr = addrinfo[0][4]
        # Treat Azure messed-up address lookup as a closed port.
        if sockaddr[0] == '0.0.0.0':
            if closed:
                return
            else:
                continue
        conn = socket.socket(*addrinfo[0][:3])
        conn.settimeout(max(remaining or 0, 5))
        try:
            conn.connect(sockaddr)
        except socket.timeout:
            if closed:
                return
        except socket.error as e:
            if e.errno not in (errno.ECONNREFUSED, errno.ENETUNREACH,
                               errno.ETIMEDOUT, errno.EHOSTUNREACH):
                raise
            if closed:
                return
        except socket.gaierror as e:
            print_now(str(e))
        except Exception as e:
            print_now('Unexpected {!r}: {}'.format((type(e), e)))
            raise
        else:
            conn.close()
            if not closed:
                return
            sleep(1)
    raise PortTimeoutError('Timed out waiting for port.')


class PortTimeoutError(Exception):
    pass
