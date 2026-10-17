# Legacy plans, sequences and plan observation

This chapter covers the older autosave plan API on the control channel. It includes the plan
store (`set_plan`, `import_plan`, `list_plan` and their getters and editors), the single-target
sequence list and its settings, the legacy plan events, and the getters a client uses to watch
any plan. The newer ViewPlan scheduler is specified in [plan-scheduling.md](plan-scheduling.md).
Below this layer sit the request/reply envelope in [session-handshake.md](session-handshake.md)
and the event framework in [events-overview.md](events-overview.md). Per-method detail lives on
the cards under `docs/control/methods/`.

Basis for the whole chapter: static analysis of firmware 9.31 (64-bit build; 32-bit build
probable) and app 3.3.2, unless a line says otherwise.

## Conventions

The key words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119 and RFC 8174. They bind
clients. Sentences about what "the device" does are descriptions.

Labels follow [CONVENTIONS.md](../../CONVENTIONS.md): **READ** (seen in firmware by static
analysis), **OBSERVED(date)** (seen on a live device), **INFERRED** (a consequence, not seen
directly), **unresolved** (not established). Integers are signed 32-bit on the device. Reals have
32-bit float precision. Error codes and messages are those of the common error table.

## Contents

- [Plans](legacy-plans-and-sequences/plans.md)
- [Sequences](legacy-plans-and-sequences/sequences.md)
- [Events and observation](legacy-plans-and-sequences/events-and-observation.md)

## Relocated sections

These anchors retain navigation from generated cards; the linked sections are the primary text.

<a id="41-set_plan-and-import_plan"></a>

- [`set_plan` and `import_plan`](legacy-plans-and-sequences/plans.md#set_plan-and-import_plan)

<a id="42-selectors"></a>

- [Selectors](legacy-plans-and-sequences/plans.md#selectors)

<a id="5-the-stand-alone-sequence-list"></a>

- [The stand-alone sequence list](legacy-plans-and-sequences/sequences.md#the-stand-alone-sequence-list)

<a id="52-sequence-settings"></a>

- [Sequence settings](legacy-plans-and-sequences/sequences.md#sequence-settings)

<a id="6-legacy-plan-reply-format"></a>

- [Legacy plan reply format](legacy-plans-and-sequences/events-and-observation.md#legacy-plan-reply-format)

<a id="7-legacy-plan-events"></a>

- [Legacy plan events](legacy-plans-and-sequences/events-and-observation.md#legacy-plan-events)

<a id="8-observing-plans"></a>

- [Observing plans](legacy-plans-and-sequences/events-and-observation.md#observing-plans)

<a id="9-viewplan-wide-camera-helpers"></a>

- [ViewPlan wide-camera helpers](legacy-plans-and-sequences/events-and-observation.md#viewplan-wide-camera-helpers)

