import collections
import paramiko
from commcare_cloud.commands.command_base import CommandBase
from commcare_cloud.commands.inventory_lookup.getinventory import get_instance_group
from commcare_cloud.environment.main import get_environment


class PrivilegedCommands():
    """
    This Class allows to execute sudo commands over ssh.
    """
    def __init__(self, user_name, password, privleged_command):
        self.user_name = user_name
        self.password = password
        self.privileged_command = privleged_command if privleged_command.startswith('sudo') \
            else 'sudo ' + privleged_command

    def run(self, host_address):
        """

        :param host_address: Address of host where command should be run.
        :type host_address: str
        :return: output of command in list format
        """
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host_address, username=self.user_name, password=self.password)
        stdin, stdout , stderr = ssh.exec_command(self.privileged_command, get_pty=True)
        stdin.write(self.password + '\n')
        stdin.flush()
        output = stdout.read().splitlines()
        if output[0].startswith('[sudo]'):
            output = output[1:]  # Ignore sudo prompt.
        return output


class ListDatabases(CommandBase):
    command = 'list-databases'
    help = """

    Example:

    To list all database on a particular server or group

    ```
    commcare-cloud staging list-databases
    ```
    """

    def run(self, args, manage_args):
        # Initialize variables
        dbs_expected_on_host = collections.defaultdict(list) # Database that should be in host
        dbs_present_in_host = collections.defaultdict(list) # Database that are in host

        args.server = 'postgresql'
        ansible_username = 'ansible'
        command = "sudo -iu postgres python /tmp/db-tools.py  --list-all"

        environment = get_environment(args.env_name)
        ansible_password = environment.get_ansible_user_password()
        host_addresses = get_instance_group(args.env_name, args.server)

        privileged_command = PrivilegedCommands(ansible_username, ansible_password, command)

        # List from Postgresql query.
        for host_address in host_addresses:
            output = privileged_command.run(host_address)
            for database in output:
                dbs_present_in_host[host_address].append(database)

        # List from Generated Mapping
        dbs = environment.postgresql_config.to_generated_variables()['postgresql_dbs']['all']
        for db in dbs:
            dbs_expected_on_host[db['host']].append(db['name'])

        # Printing
        for host_address in dbs_present_in_host.keys():
            print(host_address+ ":")
            print(" "*4 + "Expected Databases:")
            for database in dbs_expected_on_host[host_address]:
                print(" "*8 + "- " + database)

            print(" "*4 + "Additional Databases:")
            for database in dbs_present_in_host[host_address]:
                if database not in dbs_expected_on_host[host_address]:
                    print(" "*8 + "- " + database)


