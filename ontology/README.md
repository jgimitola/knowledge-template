# {{PROJECT_NAME}} ontology

The vocabulary every `spec.ttl` is written against. `ontology/{{ONTOLOGY_FILE}}` is the
machine-readable version; this page is what it means.

Replace this page as your vocabulary grows. `ontology/AUTHORING.md` explains how to design
one, and `ontology/examples/webapp.ttl` is a vocabulary that has survived real use.

## Classes

| Class     | What it is                                                       |
| --------- | ---------------------------------------------------------------- |
| `Concept` | A thing the domain is about, independent of how it is presented. |
| `Rule`    | A constraint or invariant the domain enforces.                   |
| `Actor`   | Who performs something.                                          |

## Properties

| Property      | Domain    | Range     | Notes                                                    |
| ------------- | --------- | --------- | -------------------------------------------------------- |
| `relatesTo`   | `Concept` | `Concept` | Read as symmetric; the reverse triple is not inferred.   |
| `constrains`  | `Rule`    | —         | Values span more than one type, so no range is declared. |
| `performedBy` | —         | `Actor`   |                                                          |

## Naming

Fill in the naming conventions your vocabulary uses, and encode them in
`[vocabulary] field_name_pattern` and `underscore_reserved` so `validate --strict` enforces
them rather than trusting them.
