import os
import sys

import paramiko

HOST = os.environ.get("DEPLOY_HOST") or sys.exit(
    "Zet DEPLOY_HOST (bv. via 'source deploy.local.sh')"
)
USER = "stef"
PASSWORD = os.environ["SSH_PASSWORD"]
REMOTE_TMP = "/home/stef/caddy-site-upload"
REMOTE_WEB = "/var/www/html"
LOCAL = os.path.dirname(os.path.abspath(__file__))


def upload(sftp, local_path, remote_path):
    if os.path.isdir(local_path):
        try:
            sftp.mkdir(remote_path)
        except OSError:
            pass
        for name in os.listdir(local_path):
            if name.endswith(".py") or name == "deploy.ps1":
                continue
            upload(sftp, os.path.join(local_path, name), f"{remote_path}/{name}")
    else:
        print(f"Uploading {os.path.basename(local_path)}")
        sftp.put(local_path, remote_path)


def run_sudo(client, command):
    stdin, stdout, stderr = client.exec_command(
        f"echo '{PASSWORD}' | sudo -S {command}"
    )
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out, end="")
    if err and "password for" not in err.lower():
        print(err, file=sys.stderr, end="")


def main():
    transport = paramiko.Transport((HOST, 22))
    transport.connect(username=USER, password=PASSWORD)

    client = paramiko.SSHClient()
    client._transport = transport
    sftp = paramiko.SFTPClient.from_transport(transport)

    try:
        run_sudo(client, f"rm -rf {REMOTE_TMP}")
        run_sudo(client, f"mkdir -p {REMOTE_TMP}")
        run_sudo(client, f"chown stef:stef {REMOTE_TMP}")
        upload(sftp, LOCAL, REMOTE_TMP)

        run_sudo(client, f"cp {REMOTE_TMP}/index.html {REMOTE_WEB}/")
        run_sudo(client, f"cp -r {REMOTE_TMP}/css {REMOTE_WEB}/")
        run_sudo(client, f"cp -r {REMOTE_TMP}/js {REMOTE_WEB}/")
        run_sudo(client, f"chown -R caddy:caddy {REMOTE_WEB}")
        run_sudo(client, f"chmod -R 755 {REMOTE_WEB}")
        run_sudo(client, f"rm -rf {REMOTE_TMP}")

        stdin, stdout, stderr = client.exec_command(f"ls -la {REMOTE_WEB}")
        print(stdout.read().decode())
        print("Upload complete")
    finally:
        sftp.close()
        transport.close()


if __name__ == "__main__":
    main()