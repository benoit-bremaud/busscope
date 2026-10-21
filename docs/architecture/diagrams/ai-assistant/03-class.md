# AI assistant — classes (#83)

```mermaid
classDiagram
    class ProviderSpec {
        <<frozen dataclass>>
        +id: str
        +label: str
        +default_model: str
        +needs_key: bool
        +key_url: str
        +key_hint: str
        +key_pattern: str
        +default_endpoint: str
        +key_looks_valid(key) bool
    }
    class LlmProvider {
        <<Protocol>>
        +complete(system, prompt, model, key: str|None) str
    }
    class KeyStore {
        <<Protocol>>
        +get(provider_id) str|None
        +set(provider_id, key)
        +delete(provider_id)
    }
    class RedactionOptions {
        <<frozen dataclass>>
        +anonymise_addresses: bool = True
        +relative_time: bool = True
        +mask_undecoded_payloads: bool = True
        +max_frames: int = 200
    }
    class Redactor {
        +redact(frames, options) str
    }
    class DiagnosisRequest {
        <<frozen dataclass>>
        +question: str
        +context: str
        +prompt() str
    }
    class DiagnosisService {
        +prepare(question, frames, options) DiagnosisRequest
        +ask(request, spec, model) str
        +test_connection(spec, model) str
    }
    class ProviderError
    class AnthropicProvider
    class OpenAiCompatibleProvider
    class GoogleProvider
    class KeyringKeyStore
    class AssistantWidget {
        +refresh()
        +save_key()
        +forget_key()
        +test_connection()
        +prepare()
        +send()
    }
    class build_provider {
        <<function>>
        +build_provider(provider_id, endpoint, opener) LlmProvider
    }

    AssistantWidget --> DiagnosisService
    AssistantWidget --> KeyStore
    AssistantWidget ..> build_provider
    build_provider ..> LlmProvider
    DiagnosisService --> Redactor
    DiagnosisService --> KeyStore
    DiagnosisService --> LlmProvider
    DiagnosisService ..> ProviderSpec
    DiagnosisService ..> DiagnosisRequest
    Redactor ..> RedactionOptions
    LlmProvider <|.. AnthropicProvider
    LlmProvider <|.. OpenAiCompatibleProvider
    LlmProvider <|.. GoogleProvider
    KeyStore <|.. KeyringKeyStore
    LlmProvider ..> ProviderError
```

Each adapter is built with its `base_url` and a 60 s timeout. `OpenAiCompatibleProvider` serves OpenAI, Mistral and Local (Ollama `/v1`) — same wire format,
different base URL. Adapters use the stdlib HTTP client (`urllib`), no vendor SDK.

Providers are a flat, immutable registry of `ProviderSpec` — deliberately **not** nodes of the
#77 inheritable tree (no inheritance need; YAGNI).
