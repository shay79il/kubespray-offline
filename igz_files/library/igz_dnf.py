#!/usr/bin/python
# Rocky 8 / EL8: run dnf via subprocess so Ansible 11 + python3.9 works without python3-dnf bindings.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: igz_dnf
short_description: Install/remove packages with dnf subprocess on EL8
options:
  name:
    description: Package name or list of names
    required: true
  state:
    choices: [present, absent, latest]
    default: present
  update_cache:
    type: bool
    default: false
"""

from ansible.module_utils.basic import AnsibleModule


def _normalize_names(raw):
    if raw is None:
        return []
    if isinstance(raw, list):
        names = raw
    else:
        names = [raw]
    return [str(name) for name in names if name]


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type="raw", required=True),
            state=dict(default="present", choices=["present", "absent", "latest"]),
            update_cache=dict(type="bool", default=False),
        ),
        supports_check_mode=True,
    )

    names = _normalize_names(module.params["name"])
    if not names:
        module.exit_json(changed=False)

    state = module.params["state"]
    stdout = ""
    stderr = ""

    if module.params["update_cache"]:
        rc, out, err = module.run_command(["dnf", "makecache", "-y"])
        stdout += out
        stderr += err
        if rc != 0:
            module.fail_json(msg="dnf makecache failed", rc=rc, stdout=stdout, stderr=stderr)

    if state == "absent":
        cmd = ["dnf", "remove", "-y"] + names
        if module.check_mode:
            cmd = ["dnf", "remove", "--assumeno"] + names
        rc, out, err = module.run_command(cmd)
        stdout += out
        stderr += err
        if rc != 0:
            module.exit_json(changed=False, stdout=stdout, stderr=stderr, rc=rc)
        module.exit_json(changed=True, stdout=stdout, stderr=stderr, rc=rc)

    if state == "latest":
        cmd = ["dnf", "upgrade", "-y"] + names
        if module.check_mode:
            cmd = ["dnf", "upgrade", "--assumeno"] + names
        rc, out, err = module.run_command(cmd)
        stdout += out
        stderr += err
        if rc != 0:
            module.fail_json(msg="dnf command failed", rc=rc, stdout=stdout, stderr=stderr)
        module.exit_json(changed=True, stdout=stdout, stderr=stderr, rc=rc)

    changed = False
    for pkg in names:
        cmd = ["dnf", "install", "-y", pkg]
        if module.check_mode:
            cmd = ["dnf", "install", "--assumeno", pkg]
        rc, out, err = module.run_command(cmd)
        stdout += out
        stderr += err
        lowered = out.lower()
        if rc == 0:
            if not any(token in lowered for token in ("nothing to do", "already installed")):
                changed = True
            continue
        if "already installed" in lowered:
            continue
        module.fail_json(msg="dnf command failed", rc=rc, stdout=stdout, stderr=stderr, pkg=pkg)

    module.exit_json(changed=changed, stdout=stdout, stderr=stderr, rc=0)


if __name__ == "__main__":
    main()
