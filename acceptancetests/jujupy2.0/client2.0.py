from contextlib import contextmanager
import json
from locale import getpreferredencoding
import logging
from tempfile import mkdtemp
import os
from shutil import rmtree
import subprocess
import sys

"""
The shit we really care about:
    Hook into existing controller OR bootstrap our own.
        Init a client object -> client.bootstrap(name, default model, config)
            bootstrap sets controller name to BS name
            adds a model with default model name & config
            waits for finish - SEE TIMEOUTS BELOW
        Init a client object -> client.connect_to_existing()
            connect_to_existing sets controller name to current controller
            in env and pulls models, active model
    tracking models/controllers:
        client object, which has model objects:
            client:
                stores controller name
                stores its models
                has juju() method:
                    run on current model?
                    juju(command, (args,))
                    ^ calls _juju(target, command, args)
            models:

    running juju commands via the cli:
        need a cli wrapper in the form of client.juju('command', (args,))
    tracking state of machines?
        how do we do this now?
    logs
    reading/parsing status into something machine readable

    timeouts on the above:
        wait_for_state(state)
        bootstrapping
        depoying
        etc.
        This is the hard bit


"""

log = logging.getLogger('jujupy')


class JujuClient:

    def __init__(self):
        self.name = self._get_controller_name()
        self.models = set(self._get_current_models)
        self.active_model = self._get_active_model()

    def juju(self, command, args, get_output=False):
        """Runs a command against the current juju model"""
        if get_output:
            call = subprocess.check_output
        else:
            call = subprocess.call
        try:
            return call('juju', command, args).decode('UTF-8')
        except subprocess.CalledProcessError as e:
            log.error('Juju call: {} failed with error: {}'.format(command, e))
            raise(e)

    def add_model(self, model):
        new_model = JujuModel(model)
        self.juju('add-model', (model,))
        self.models.add(new_model)
        self.active_model = new_model

    def switch_model(self, target_model):
        """Switches current model to target_model

        :param target_model: JujuModel object
        """
        self.juju('switch', (target_model.name))
        self.active_model = target_model

    def deploy(self, charm, num=1, to=None):
        """Deploy a charm to the current model"""
        args = (charm,)
        if num:
            args += ('-n', num)
        if to:
            args += ('--to', to)
        self.juju('deploy', args)

    def status(self):
        """Returns json formatted status for active model"""
        status_raw = self.juju('status', ('--format', 'json'))
        status = json.loads(status_raw)
        return status

    def dump_logs(self):
        """Contact machines, controller & pull logs

        Pulls status, gets machines. SCP /var/log/whatever off each machine
        tar up the logs by machine
        SCP /var/log/whatever off controller machines
        """
        machines = self.status().get('machines')
        for machine, info in machines.keys():
            pass

    @classmethod
    def _get_active_model(self):
        """Gets the active model for the current Juju controller
        """
        return self.juju()

    def _get_current_models(self):
        """Gets the current models when controller object was intialized"""
        return None


class JujuModel:

    def __init__(self, name):
        self.name = name
