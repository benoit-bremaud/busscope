# Individual module measurements specification

> **Feature**: issue #3 — [Decode individual charger module measurements](https://github.com/benoit-bremaud/busscope/issues/3)
> **Source**: Infypower *Charger module CAN Communication Protocol V1.13*, section 2.3, command `0x03`

## Scope

This feature decodes the output voltage and output current returned by one charger module.
It is a read-only protocol concern and does not send the corresponding read request or any
other CAN frame.

## Identifier semantics

The response uses a 29-bit extended Infypower identifier. The destination address identifies
the queried module and the source address identifies the responder. The identifier is decoded
by the existing `ProtocolDecoder` before command-specific payload decoding.

## Payload mapping

The response data field is exactly eight bytes:

| Bytes | Field | Encoding | Unit |
| --- | --- | --- | --- |
| 0-3 | Module output voltage | IEEE-754 binary32, big-endian | V |
| 4-7 | Module output current | IEEE-754 binary32, big-endian | A |

The protocol example is:

```text
Response: 02 83 F0 00 43 FA 00 00 40 60 00 00
Voltage: 500 V
Current: 3.5 A
```

The four identifier bytes are shown together with the eight-byte data field in the source
document. The domain model receives only the eight-byte CAN payload.

## Invalid input behavior

- A payload whose length is not eight bytes is preserved as a raw frame and produces an
  `Expected an 8-byte payload` diagnostic.
- A frame with a non-extended identifier is preserved and produces an extended-identifier
  diagnostic without attempting command decoding.
- A CAN controller error frame is preserved and produces an error-frame diagnostic.

## Implementation mapping

`ModuleMeasurements` is a typed domain value containing voltage in volts and current in
amperes. `DecodeResult` preserves the original `CanFrame` and exposes the decoded value only
when the identifier is command `0x03` and the payload is valid.

## Verification

The unit test uses the protocol example and checks `500.0 V` and `3.5 A`. The shared decoder
tests cover invalid frame metadata and payload lengths. The feature remains independent of
`python-can`, SocketCAN, PySide6, and filesystem I/O.
