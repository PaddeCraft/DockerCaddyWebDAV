import subprocess
import textwrap
import tomllib
import shutil
import os


def indent(text, amount):
    return textwrap.indent(text, " " * (amount * 4))


print("Loading config... ", end="")

if not os.path.exists("/config/config.toml"):
    # Copy default config
    shutil.copyfile("/app/config.example.toml", "/config/config.toml")
    print("Config not found. Default config copied to /config/config.toml")
    exit(1)

with open("/config/config.toml", "rb") as f:
    config = tomllib.load(f)

print("Done.")

enable_web = config.get("enable_web", True)
use_https = config.get("use_https", False)
if use_https:
    domain = config.get("domain", "localhost")
else:
    domain = config.get("domain", "*")

users_cfg = config.get("user", [])
shares = config.get("share", [])

users = []
for user in users_cfg:
    if not "username" in user:
        print("Username is required")
        exit(1)

    username = user["username"]

    if "password" in user:
        # Run caddy hash-password to hash password
        password_hash = (
            subprocess.run(
                ["caddy", "hash-password", "--plaintext", user["password"]],
                capture_output=True,
            )
            .stdout.decode()
            .strip()
        )

    elif "password_hash" in user:
        password_hash = user["password_hash"]

    else:
        print("Password or password hash is required")
        exit(1)

    users.append({"username": username, "password_hash": password_hash})
    print(f"Registered user: {username}")


caddy_file = f"""\
# This file was automatically generated. Any changes will be overwritten.
# To change the configuration, edit /config/config.toml
# and restart the container.

# Begin config
http{'s' if use_https else ''}://{domain} {{
"""
for share in shares:
    print(f"Registering share: {share['name']}... ", end="")
    if not share.get("name"):
        print("Share name is required")
        exit(1)

    if not share.get("path"):
        print("Share path is required")
        exit(1)

    if not os.path.isabs(share["path"]):
        print("Share path must be absolute")
        exit(1)

    share_path = "/filesystem" + share["path"]
    share_route = "/share/" + share["name"]

    use_auth = "access" in share

    caddy_file += f"    # Share: {share['name']}\n"
    caddy_file += f"    # Access control: {'enabled' if use_auth else 'disabled'}, Real path: {share['path']}\n"
    caddy_file += f"    route {share_route}* {{\n"

    auth = ""

    if use_auth:
        access = share["access"]
        read = access.get("read", [])
        read_write = access.get("read_write", [])

        # Remove all users from read that are in read_write, since they already have read access
        read = [x for x in read if x not in read_write]

        # Get users from global definition
        read = [x for x in users if x["username"] in read]
        read_write = [x for x in users if x["username"] in read_write]

        auth += f"        basicauth {{\n"

        if len(read_write) > 0:
            auth += f"            # Read-write access\n"
        for user in read_write:
            auth += f"            {user['username']} {user['password_hash']}\n"

        if len(read) > 0:
            auth += f"            # Read access\n"
        for user in read:
            auth += f"            {user['username']} {user['password_hash']}\n"

        auth += f"        }}\n\n"

        caddy_file += auth

        # Based on https://caddy.community/t/disallow-webdav-write-http-methods-for-certain-user/20781/3
        # Only allow certain methods for certain users
        for user in read:
            caddy_file += indent(
                textwrap.dedent(
                    f"""\
                        # Limit to read access ({user['username']})
                        @prohibitWrite_{user['username']} {{
                            vars http.auth.user.id {user['username']}
                            not method GET HEAD OPTIONS PROPFIND
                        }}
                        handle @prohibitWrite_{user['username']} {{
                            respond "Forbidden" 403
                        }}\n\n"""
                ),
                2,
            )

    caddy_file += indent(f"rewrite {share_route} {share_route}/\n", 2)
    caddy_file += indent(
        textwrap.dedent(
            f"""
                # WebDAV
                webdav {{
                    root {share_path}
                    prefix {share_route}
                }}
                """
        ),
        2,
    )

    caddy_file += "    }\n\n"

    # Web UI
    if enable_web:
        caddy_file += f"    handle_path /browse/{share['name']}* {{\n"
        caddy_file += auth
        caddy_file += f"        root * {share_path}\n"
        caddy_file += f"        file_server browse\n"
        caddy_file += f"    }}\n\n"

    print("Done.")

caddy_file += "}\n# End config\n"

print("\n\nConfig:")
print(caddy_file)
print("\n\n")

print("Writing config... ", end="")
with open("/app/Caddyfile", "w") as f:
    f.write(caddy_file)
print("Done.")

# Run caddy
subprocess.run(["caddy", "run", "--config", "/app/Caddyfile"])
