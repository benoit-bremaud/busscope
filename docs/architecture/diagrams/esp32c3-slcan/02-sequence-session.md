# Sequence diagram — a capture session over slcan

## Context

One full session, from the application opening the serial device to the frames reaching the
decoder. The host side is python-can's slcan backend driven by `PythonCanAdapter`; nothing in
the application is specific to this firmware, which is the point of implementing the protocol
rather than inventing one.

## Diagram

```mermaid
sequenceDiagram
    participant App as busscope
    participant Bus as python-can slcan
    participant Codec as slcan codec
    participant Port as TwaiPort
    participant CAN as CAN bus

    App->>Bus: open(channel, bitrate, listen_only)
    Bus->>Codec: C
    Codec->>Port: stop, uninstall
    Codec-->>Bus: ACK

    Bus->>Codec: S&lt;n&gt;
    alt bitrate the controller can produce
        Codec-->>Bus: ACK
    else 750k or 83.3k
        Codec-->>Bus: BEL
        Note over Codec,Bus: 83.3k is absent from the SDK; 750k is worse<br/>than missing, since LAWICEL reads S7 as 800k<br/>while python-can sends it for 750. An ambiguous<br/>code is refused, never resolved by assumption
    end

    Bus->>Codec: L
    Codec->>Port: install LISTEN_ONLY, start
    Note over Port,CAN: the controller cannot transmit<br/>or acknowledge: silence is enforced<br/>by the peripheral, not promised
    Codec-->>Bus: ACK

    loop while the channel is open
        CAN-->>Port: frame
        Port-->>Codec: twai_message_t
        Codec-->>Bus: T&lt;id&gt;&lt;dlc&gt;&lt;data&gt;
        Bus-->>App: can.Message
    end

    App->>Bus: shutdown()
    Bus->>Codec: C
    Codec->>Port: stop, uninstall
    Codec-->>Bus: ACK
```

## Notes

- Every command is answered. An adapter that stays silent makes "applied" indistinguishable
  from "ignored", which is precisely what cost a full day of diagnosis on the CANable and
  what forced #48 to ship an explicit "accept unverified silence" opt-in.
- The codec never emits a line beginning with `t`, `T`, `r`, `R` or `x` other than a genuinely
  received frame, so the host can never mistake a diagnostic for traffic.
- `F` is answered from the TWAI counters with the LAWICEL status byte. It is polled, not
  pushed: slcan carries no error frame, and no firmware can change that.
- The receive loop is bounded per iteration and the driver queue is deeper than the bench
  profiles need, but a saturated bus will still drop frames, silently, as slcan always does.
