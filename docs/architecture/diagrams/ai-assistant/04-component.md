# AI assistant — components (#83)

```mermaid
flowchart TB
    subgraph UI [Qt boundary]
        panel[ai_assistant_ui.py<br/>AssistantPanel]
    end
    subgraph Domain [Qt-free, network-free]
        dom[ai_assistant.py<br/>ProviderSpec, Redactor,<br/>DiagnosisService, ports]
    end
    subgraph Adapters [I/O boundary]
        http[ai_providers.py<br/>HTTP adapters]
        kr[ai_keystore.py<br/>KeyringKeyStore]
    end
    cloud[(Anthropic / OpenAI /<br/>Mistral / Google APIs)]
    local[(Ollama / local endpoint)]
    secret[(Secret Service)]

    panel --> dom
    panel --> http
    panel --> kr
    http -. implements port .-> dom
    kr -. implements port .-> dom
    http --> cloud
    http --> local
    kr --> secret
```

Dependency rule: `ai_assistant.py` imports nothing from PySide6, `keyring` or `urllib`.
Non-secret choices (provider, model, endpoint) persist via the existing QSettings adapter.
The capture frames reach the panel via the existing session model; the assistant has no
access to transmission.
