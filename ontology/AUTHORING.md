# Authoring an ontology

`ontology/ontology.ttl` ships with three classes and three properties — enough to write a
first spec against, not enough to describe a real domain. This page is how you grow it, and
why the choices below look the way they do. `ontology/examples/webapp.ttl` is a full-sized
vocabulary that grew this way; the snippets below borrow its `web:` terms.

## Design from the domain, not the tooling

The seed's classes — `Concept`, `Rule`, `Actor` — are deliberately generic. They are not a
skeleton to fill in; they are what is left after everything domain-specific has been removed.
Your real ontology should not look like the seed with names swapped in.

Start from the nouns and verbs the people who know the domain actually use, out loud, when
they describe it to each other — not from a modelling textbook's idea of what a class should
be. If the domain is a web application, the people who build it talk about screens, the
things on those screens, and what a user can do with them — which is why
`ontology/examples/webapp.ttl` has `View`, `Section`, `Field` and `Action` instead of one
catch-all `Thing`. If your domain is a logistics pipeline, its ontology should have the nouns
a dispatcher uses, not `View` and `Section`.

Delete every seed term your domain has no use for. A class nobody ever instantiates, or a
property nobody ever asserts, is not a harmless placeholder — it is a question every reader
of `ontology/README.md` has to stop and answer ("do we use this?") for no reason.

## Naming conventions

`ontology/README.md`'s naming table is a promise to whoever writes the next spec. Written
down as prose, it is a promise nothing checks — a reviewer has to notice the drift by eye.
Two `[vocabulary]` keys turn the same promise into something `validate --strict` enforces
mechanically:

```toml
field_name_pattern  = "^[A-Z][A-Za-z0-9]*_[a-z][A-Za-z0-9]*$"
underscore_reserved = true
```

`field_name_pattern` is a regular expression every instance of `field_class` must match by
its local name — `^[A-Z][A-Za-z0-9]*_[a-z][A-Za-z0-9]*$` reads as "the owning class, then an
underscore, then the field name in camelCase": `View_route`, `Field_defaultsTo`.
`underscore_reserved` then extends the same convention the other way: if the underscore means
"this is a field", nothing that is _not_ a field should use one — an instance named
`payment_method` instead of `paymentMethod` is a naming violation even though no pattern was
written for it, because the check reserves the underscore for `field_class` alone.

Both are opt-in and independent. Leave `field_class` empty and neither runs — see the closing
checklist below for what each key needs configured before it does anything.

## `partOf` is not transitive, on purpose

`ontology/examples/webapp.ttl` declares `web:partOf` and its reading inverse `web:contains`,
and its comment says outright: _"Not transitive. For the whole chain use the property path
`web:partOf+`."_ That is a design decision, not an omission.

RDFS (which is all this tooling's checks reason over — there is no OWL reasoner here) has no
built-in notion of a transitive property; declaring one transitive would need `owl:`, and
even then it would mean every `partOf` assertion silently implies every indirect one, which
is rarely what a rule that says "constrains everything directly inside this section" wants.
Keeping `partOf` non-transitive keeps direct containment and the whole-chain question two
different questions, asked two different ways. Direct containment is one triple:

```sparql
SELECT ?child WHERE { ?child web:partOf app:Dashboard }
```

The whole chain — everything nested at any depth — is a property path, spelled with the `+`
one-or-more operator, asked for explicitly rather than assumed:

```sparql
SELECT ?descendant WHERE { ?descendant web:partOf+ app:Dashboard }
```

## Inverse pairs are a convention, not an inference

`web:contains` is documented as "the reading inverse of `web:partOf`" — but nothing makes that
true automatically. Without OWL's `owl:inverseOf`, asserting `app:Widget web:partOf
app:Dashboard` does not produce the triple `app:Dashboard web:contains app:Widget`; if a spec
only ever asserts one direction (and most do — writing both is a redundant ceremony most
specs skip), a query that only reads the other direction misses everything.

A query that has to be right regardless of which direction a spec actually used asks both, in
one pattern, with a property-path alternation — `|` for "either predicate", `^` to reverse a
predicate's direction:

```sparql
SELECT ?child WHERE { app:Dashboard (web:contains|^web:partOf) ?child }
```

That reads as "either an outgoing `contains`, or an incoming `partOf` read backwards" — so it
finds `?child` whichever direction the spec's author happened to assert.

## A property whose values span two types gets no `rdfs:range`

The seed's `ex:constrains` declares `rdfs:domain ex:Rule` and no `rdfs:range` at all, and its
comment explains why: _"the values span more than one type, and two ranges would be read as
requiring both at once."_ That is real RDFS semantics — under a reasoner, two `rdfs:range`
triples on the same property are two constraints that both hold, so a fully-entailed value
would need to be a member of the intersection of both classes, not either one.

But `lint.domain_range_violations` is not a reasoner, and the mistake to avoid is assuming it
enforces that intersection. It does not — it builds the declared ranges into a set and flags
an assertion only when the object's _actual_ type shares nothing with that set:

```turtle
ex:touches a rdf:Property ; rdfs:range ex:Field, ex:Concept .

app:X a ex:Field ;   ex:touches app:F .   # app:F typed only ex:Field
app:Y a ex:Field ;   ex:touches app:C .   # app:C typed only ex:Concept
```

```
domain_range_violations(...) -> []
```

Neither assertion is flagged: `app:F`'s type (`Field`) intersects the declared range set, and
so does `app:C`'s (`Concept`) — each individually satisfies _some_ member of the set, which is
enough for the checker's set-intersection test to pass. Two ranges do not turn the check red;
they make it permissive. It silently accepts anything typed as either declared class, and a
reader looking only at the ontology (not this checker's source) has every reason to expect the
stricter, textbook reading — both at once — and be surprised when nothing actually enforces
it. That gap between what `rdfs:range Field, Concept` looks like it promises and what the
checker actually lets through is the real argument for leaving the range off: a declared range
that does not mean what a reader assumes it means is worse than no declared range at all.

The fix is to declare no `rdfs:range` at all, and say in `rdfs:comment` what the property
actually allows, in prose a reader can act on but the checker leaves alone:

```turtle
ex:constrains a rdf:Property ;
    rdfs:label   "constrains"@en ;
    rdfs:domain  ex:Rule ;
    rdfs:comment "What the rule restricts. No rdfs:range: the values span more than one type, and two ranges would be read as requiring both at once."@en .
```

## Functional properties, and how `contradictions` uses them

A property is functional when the domain itself allows at most one value — a view has one
route, a field has one default. RDFS does not enforce this on its own (that, too, is an OWL
notion, `owl:FunctionalProperty`, and this tooling does not load OWL), so nothing stops two
`web:route` triples from being asserted on the same view by two different specs, or by the
same spec at two different times, without either author noticing.

Listing the property in `[vocabulary] functional_properties` is what gives
`knowledge contradictions` something to check:

```toml
functional_properties = ["route", "editable", "required", "viewport", "defaultsTo"]
```

With `route` listed, `contradictions.functional_conflicts` groups every triple by (subject,
property) and flags any group with more than one distinct value — two different routes
asserted for the same view is now a contradiction the command reports, not a fact that
silently sits in the graph until a query happens to notice both values.

## `verbatim_string_properties`: only for literal text, never a paraphrase

`lint.ungrounded_literals` checks that a property's literal value appears, character for
character (whitespace-collapsed), somewhere in that spec's `spec.md` prose. That only makes
sense for a predicate whose value _is_ the exact text a reader would see — `web:emptyState
"Add your first item to get started."` is the literal copy the interface shows, so it should
appear verbatim in the prose describing that screen.

It does not make sense for a predicate whose value is something the writer composed in their
own words — `rdfs:comment` is exactly this: a paraphrase, a summary, an explanation. Put a
paraphrasing predicate in `verbatim_string_properties` and every value it has ever been given
gets flagged as "ungrounded", because a paraphrase is, by construction, never a verbatim
substring of the prose it paraphrases. The check would be permanently red for a predicate that
was never wrong — the same failure mode as declaring two ranges above, for the same underlying
reason: a check configured to run against the wrong kind of value cannot pass, no matter how
correct the graph is.

```toml
verbatim_string_properties = ["emptyState"]
```

## Checklist: every new term, and the key that makes a check see it

Adding a class or property to the ontology does not, by itself, make any check aware of it.
Each mechanical check reads specific `[vocabulary]` keys; a term the checks should reason
about needs to be named in the matching key, or it is invisible to `validate --strict` and
`knowledge contradictions` alike.

| You added...                                         | Configure...                                     | So that...                                                                                                    |
| ---------------------------------------------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------- |
| A class marking a domain rule                        | `rule_class`                                     | `restated_rule_comments` requires every instance to carry a real reason, not a restated label.                |
| A class marking a reusable domain concept            | `concept_class` and `concept_spec`               | `locally_redeclared_concepts` catches the same concept declared on two specs instead of referenced from one.  |
| A class marking a field or datum                     | `field_class`                                    | `naming_violations` has something to apply `field_name_pattern` and `underscore_reserved` to.                 |
| A property that should have at most one value        | `functional_properties`                          | `knowledge contradictions` flags a second value as a conflict instead of accepting both.                      |
| A property whose value is verbatim UI or domain text | `verbatim_string_properties`                     | `ungrounded_literals` can confirm the graph and the prose still agree.                                        |
| Any class or property at all                         | (nothing — declared in `ontology.ttl` is enough) | `invented_predicates` / `invented_types` stop flagging it as undeclared the moment it exists in the ontology. |

A term left out of every relevant key is not broken — it is simply unchecked. `validate
--strict` reports the corresponding check as `skipped (not configured)` rather than pretending
it passed, which is the honest state for a vocabulary that has not told the tooling about that
term yet.
