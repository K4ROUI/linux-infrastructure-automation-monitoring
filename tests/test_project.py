"""Tests statiques du laboratoire (aucun Docker, ni sudo, ni SSH requis)."""
import json
from pathlib import Path
import re
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


def contents(path):
    return (ROOT / path).read_text(encoding='utf-8')


def parsed(path):
    return yaml.safe_load(contents(path))


class ProjectStructure(unittest.TestCase):
    def test_expected_files_are_present(self):
        required = [
            'README.md', 'compose.yaml', '.gitignore', '.env.example', 'requirements-dev.txt',
            'docker/ubuntu-host/Dockerfile', 'docker/ubuntu-host/entrypoint.sh',
            'docker/ubuntu-host/ssh-hardening.conf',
            'docker/ubuntu-host/supervisor-lab.conf',
            'ansible/inventory.ini', 'ansible/site.yml',
            'ansible/templates/nginx-site.conf.j2', 'ansible/templates/index.html.j2',
            'monitoring/prometheus/prometheus.yml',
            'monitoring/prometheus/alerts.yml',
            'monitoring/alertmanager/alertmanager.yml',
            'monitoring/blackbox/blackbox.yml',
            'monitoring/grafana/provisioning/datasources/prometheus.yml',
            'monitoring/grafana/provisioning/dashboards/default.yml',
            'monitoring/grafana/dashboards/linux-infra.json',
            'scripts/lab.sh', 'scripts/backup.sh', 'scripts/restore.sh',
            'scripts/check_metrics.py', 'scripts/check_alert.py',
            '.github/workflows/ci.yml',
            'docs/architecture.md', 'docs/operations.md', 'docs/validation.md',
        ]
        for file in required:
            with self.subTest(file=file):
                self.assertTrue((ROOT / file).is_file(), f'Fichier manquant : {file}')

    def test_no_secrets_in_repository(self):
        self.assertFalse((ROOT / '.env').exists())
        self.assertFalse((ROOT / '.secrets').exists())
        ignored = contents('.gitignore')
        self.assertIn('.env', ignored)
        self.assertIn('.secrets/', ignored)


class ComposeChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compose = parsed('compose.yaml')
        cls.services = cls.compose['services']

    def test_six_services(self):
        self.assertEqual(set(self.services), {'web', 'backup', 'prometheus',
                                             'grafana', 'blackbox', 'alertmanager'})

    def test_ubuntu_hosts_share_image_definition(self):
        for host in ('web', 'backup'):
            self.assertEqual(self.services[host]['build']['context'], './docker/ubuntu-host')
            self.assertEqual(self.services[host]['restart'], 'unless-stopped')

    def test_published_ports_are_loopback_only(self):
        for service in self.services.values():
            for port in service.get('ports', []):
                with self.subTest(port=port):
                    self.assertRegex(str(port), r'^127\.0\.0\.1:')

    def test_secrets_not_committed_in_compose(self):
        content = contents('compose.yaml')
        self.assertIn('${GRAFANA_ADMIN_PASSWORD:', content)
        self.assertIn('./.secrets/id_ed25519.pub', content)
        self.assertNotIn('id_ed25519:/', content)  # private key must never be mounted
        self.assertNotIn('admin123', content.lower())

    def test_monitored_images_not_latest(self):
        for service in ('prometheus', 'grafana', 'alertmanager', 'blackbox'):
            image = self.services[service]['image']
            self.assertIn(':', image)
            self.assertNotIn(':latest', image)

    def test_backup_is_persistent(self):
        backup_volumes = self.services['backup']['volumes']
        self.assertIn('backup_data:/srv/lab-backups', backup_volumes)
        self.assertIn('backup_data', self.compose['volumes'])


class AnsibleChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playbook = parsed('ansible/site.yml')

    def test_configuration_manages_all_hosts(self):
        self.assertEqual(self.playbook[0]['hosts'], 'lab')
        self.assertEqual(self.playbook[1]['hosts'], 'web')
        self.assertEqual(self.playbook[2]['hosts'], 'backup')

    def test_template_and_handler_are_present(self):
        content = contents('ansible/site.yml')
        self.assertIn('ansible.builtin.template:', content)
        self.assertIn('ansible.builtin.apt:', content)
        self.assertIn('notify: Recharger Nginx', content)
        self.assertIn('supervisorctl restart nginx', content)

    def test_ssh_targets_and_remote_python(self):
        config = contents('ansible/inventory.ini')
        for port in ('2221', '2222'):
            self.assertIn(f'ansible_port={port}', config)
        self.assertIn('ansible_user=labadmin', config)
        self.assertIn('ansible_python_interpreter=/usr/bin/python3', config)

    def test_ssh_hardening(self):
        ssh = contents('docker/ubuntu-host/ssh-hardening.conf')
        for setting in ('PasswordAuthentication no', 'PermitRootLogin no',
                        'KbdInteractiveAuthentication no', 'AllowUsers labadmin'):
            self.assertIn(setting, ssh)
        self.assertIn('ssh-keygen -A', contents('docker/ubuntu-host/entrypoint.sh'))


class MonitoringChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prom = parsed('monitoring/prometheus/prometheus.yml')
        cls.alert = parsed('monitoring/prometheus/alerts.yml')
        cls.dashboard = json.loads(contents('monitoring/grafana/dashboards/linux-infra.json'))

    def test_exporters_scraped(self):
        jobs = {job['job_name']: job for job in self.prom['scrape_configs']}
        self.assertIn('node-linux', jobs)
        self.assertIn('http-health', jobs)
        self.assertEqual(jobs['node-linux']['static_configs'][0]['targets'], ['web:9100', 'backup:9100'])

    def test_blackbox_http_probe_targets_web(self):
        job = next(job for job in self.prom['scrape_configs'] if job['job_name'] == 'http-health')
        self.assertEqual(job['static_configs'][0]['targets'], ['http://web:80/health'])
        self.assertEqual(job['params']['module'], ['http_2xx'])
        self.assertIn('blackbox:9115', str(job))

    def test_alert_rules_are_present(self):
        rules = self.alert['groups'][0]['rules']
        by_name = {rule['alert']: rule for rule in rules}
        self.assertIn('WebServiceUnavailable', by_name)
        self.assertIn('LinuxExporterUnavailable', by_name)
        self.assertIn('probe_success', by_name['WebServiceUnavailable']['expr'])
        self.assertEqual(by_name['WebServiceUnavailable']['for'], '20s')
        self.assertTrue(self.prom['alerting']['alertmanagers'])

    def test_alertmanager_has_no_external_receivers(self):
        receivers = parsed('monitoring/alertmanager/alertmanager.yml')['receivers']
        self.assertEqual(receivers, [{'name': 'lab-local'}])

    def test_grafana_dashboard_provisioned(self):
        dashboard = self.dashboard
        self.assertEqual(dashboard['uid'], 'linux-infra-lab')
        self.assertEqual(len(dashboard['panels']), 4)
        self.assertTrue(all(p['datasource']['uid'] == 'prometheus-lab'
                            for p in dashboard['panels']))
        ds = parsed('monitoring/grafana/provisioning/datasources/prometheus.yml')
        self.assertEqual(ds['datasources'][0]['uid'], 'prometheus-lab')
        provider = parsed('monitoring/grafana/provisioning/dashboards/default.yml')
        self.assertEqual(provider['providers'][0]['options']['path'], '/var/lib/grafana/dashboards')


class BackupAndDocsChecks(unittest.TestCase):
    def test_backup_and_restore_check_sha256(self):
        self.assertIn('sha256sum', contents('scripts/backup.sh'))
        self.assertIn('sha256sum', contents('scripts/restore.sh'))
        self.assertIn('snapshot-', contents('scripts/backup.sh'))
        self.assertRegex(contents('scripts/restore.sh'), r'\[\[ "\$ID" =~ \^snapshot-')

    def test_scripts_expose_commands(self):
        s = contents('scripts/lab.sh')
        for action in ('init', 'up', 'provision', 'test', 'backup', 'restore', 'incident', 'recover', 'status', 'down'):
            with self.subTest(action=action):
                self.assertRegex(s, rf'(?m)^  {action}\)')

    def test_no_claim_of_three_real_vms(self):
        readme = contents('README.md')
        self.assertIn('conteneurs Docker', readme)
        self.assertIn('pas des machines virtuelles', readme)
        self.assertIn('Ne pas présenter', readme)

    def test_docs_explain_the_limits(self):
        limitations = contents('docs/validation.md').lower()
        self.assertIn('conteneurs', limitations)
        self.assertIn('pas de', limitations)
        self.assertIn('sha-256', limitations)
        self.assertIn('offsite', limitations)


if __name__ == '__main__':
    unittest.main()
