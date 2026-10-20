# Release tag protection

Release tags match `refs/tags/v*`. Only repository administrators may create them, and matching
tags cannot be updated or deleted through normal repository access. This preserves released
versions as immutable references while retaining an explicit administrator bypass for releases.

## Apply

Verify that no ruleset with the same name exists, then create the active tag ruleset:

```bash
gh api repos/benoit-bremaud/busscope/rulesets \
  --paginate \
  --jq '.[] | select(.name == "Protect release tags") | {id, name, target, enforcement}'

gh api repos/benoit-bremaud/busscope/rulesets -X POST --input - <<'JSON'
{
  "name": "Protect release tags",
  "target": "tag",
  "enforcement": "active",
  "bypass_actors": [
    {
      "actor_id": 5,
      "actor_type": "RepositoryRole",
      "bypass_mode": "always"
    }
  ],
  "conditions": {
    "ref_name": {
      "include": ["refs/tags/v*"],
      "exclude": []
    }
  },
  "rules": [
    {"type": "creation"},
    {"type": "update"},
    {"type": "deletion"}
  ]
}
JSON
```

## Verify

Find the ruleset identifier, then inspect its full configuration:

```bash
gh api repos/benoit-bremaud/busscope/rulesets \
  --paginate \
  --jq '.[] | select(.name == "Protect release tags") | {id, name, target, enforcement}'

gh api repos/benoit-bremaud/busscope/rulesets/<RULESET_ID>
```

The result must target tags, use active enforcement, include `refs/tags/v*`, contain creation,
update, and deletion restrictions, and grant the administrator role an always-on bypass.

## Remove

Remove this ruleset only when replacing the policy or recovering from a documented configuration
error. Record the reason before running:

```bash
gh api repos/benoit-bremaud/busscope/rulesets/<RULESET_ID> -X DELETE
```
