I would make the refurbished library **database-first and entity-centered**, with the filesystem reduced to almost nothing more than durable blob storage. The key design choice is that I would **not make everything a tag**. Names, types, groupings, prompt text, and usage relationships deserve stronger semantics; tags should handle the flexible remainder.

That approach is consistent with established DAM practice. ResourceSpace explicitly points out that folders become limiting because an asset can belong naturally to many categories, and recommends metadata and collections instead. IPTC similarly distinguishes structured information about people/things from free-text keywords, and recommends controlled vocabularies where consistency matters. Lightroom combines keywords with collections and rule-driven smart collections. :chatgpt-content-reference{index="0"}

## The conceptual model I would use

Think of Zet's library as this graph:

```text
                         ┌──────────────┐
                         │    Entity    │
                         │  Tsaeytte    │
                         │  Morrow      │
                         │  Utility Tusk│
                         └──────┬───────┘
                                │ depicts / belongs to / uses
                                │
┌──────────────┐        ┌───────▼────────┐        ┌────────────────┐
│ Reference Set│◄──────►│     Asset      │◄──────►│      Tags      │
│ Tsaeytte Head│        │ actual image   │        │ view:front     │
│ Tusk Refs    │        │ stable ID      │        │ framing:head   │
└──────────────┘        └───────┬────────┘        │ mood:neutral   │
                                │                 └────────────────┘
                         ┌──────▼───────┐
                         │ Descriptors  │
                         │ prompt text  │
                         │ human notes  │
                         └──────┬───────┘
                                │
                         ┌──────▼───────┐
                         │    Usage     │
                         │ scene X      │
                         │ costume Y    │
                         └──────────────┘
```

The important distinction is:

**Entity = what the picture is about.**

**Asset = the particular image file.**

**Reference Set = a useful curated grouping of assets.**

**Tag = an attribute useful for filtering.**

**Descriptor = text with an explicit purpose.**

**Usage = somewhere in Zet that refers to the asset.**

That separation solves quite a few problems before they occur.

---

## 1. `Asset` should be boring

An asset represents one actual image.

I would give it approximately these properties:

| Field | Purpose |
|---|---|
| `asset_id` | Immutable UUID or similar |
| `file_path` | Current storage location |
| `filename` | Mostly informational |
| `checksum` | Detect duplicate/replaced files |
| `width`, `height` | Useful filters |
| `mime_type` | PNG, WEBP, JPEG |
| `created_at` | Library bookkeeping |
| `source_type` | Zet, Qwen, imported, edited, etc. |
| `parent_asset_id` | Optional derived-from relationship |
| `status` | candidate / approved / obsolete / archived |
| `rating` | Optional selection aid |
| `notes` | Human-only notes |

The filename and directory are **not the identity of the image**.

Everything else should refer to:

```text
asset_id = 93d9...
```

rather than:

```text
images/characters/Tsaeytte/Adult/Heads/front.png
```

That alone makes restructuring vastly safer.

The actual files could be nearly flat:

```text
library/
    images/
        019ac3....png
        019ac4....png
        019ac5....webp
```

Or lightly bucketed if the collection eventually gets huge:

```text
images/
    01/
    02/
    03/
```

I would not put meaningful taxonomy into these directories.

---

## 2. Make `Entity` first-class rather than treating names as tags

This is probably the biggest change I'd make from a pure tagging system.

These should be entities:

```text
Tsaeytte
Morrow
Valindia Vandermere
Utility Tusk
Spire of Celestial Wisdom
Canonical Adventure Gear
Tsaeytte Jewelry
Malebolge
Salamandar
```

An entity has a stable ID and a controlled type:

```text
entity
------
entity_id
name
entity_type
description
aliases
status
```

Possible types might include:

```text
character
npc
monster
creature
costume
prop
location
backdrop
vehicle
effect
symbol
```

You can extend that vocabulary later.

I would **not** put:

```text
tag = Tsaeytte
tag = character
```

on every Tsaeytte image.

Instead:

```text
asset_entity
------------
asset_id
entity_id
role
```

For example:

```text
asset_471
    primary_subject -> Tsaeytte
    costume         -> Canonical Adventure Gear
    companion       -> Morrow
    held_prop       -> Utility Tusk
```

Now the database actually understands these as separate things.

That becomes especially valuable for scenes containing multiple subjects.

---

## 3. Use tags for facets, not identity

Tags are still extremely valuable, but I'd reserve them for things where loose many-to-many categorization makes sense.

For Zet, I'd probably make tags namespaced:

```text
view:front
view:left_profile
view:front_right_3_4

framing:head
framing:half_body
framing:full_body

expression:neutral
expression:smiling
expression:angry

pose:standing
pose:seated
pose:action

background:transparent
background:neutral
background:environment

purpose:identity_reference
purpose:costume_reference
purpose:scene_reference

quality:canonical
quality:preferred

style:painterly
style:semi_realistic
```

You do not necessarily have to expose the `namespace:value` syntax in the UI. Internally, though, it is very useful.

For frequently used facets, use a **controlled vocabulary** rather than letting arbitrary strings proliferate. IPTC makes essentially this distinction: controlled terms are useful when consistency matters, while free keywords remain available for material not covered by structured fields. :chatgpt-content-reference{index="1"}

So:

```text
view = FRONT
```

should probably be a controlled tag.

Something occasional like:

```text
damaged clothing
```

can remain free-form.

This avoids eventually having:

```text
front-right
front right
FR-right
FRONT_RIGHT
front_right_3_4
front-right-3/4
```

representing one concept.

---

## 4. Add `ReferenceSet` as an explicit concept

This addresses your "several different images all relating to one thing" requirement.

A **Reference Set** is not a directory and isn't necessarily an entity.

It means:

> These assets form a useful set for some purpose.

Examples:

```text
Tsaeytte — Adult Head Reference
Tsaeytte — Canonical Adventure Gear
Tsaeytte — Armored Costume Turnaround
Morrow — Raven Form
Utility Tusk — Shape References
Spire Entrance — Background Plates
Valindia — Adult Identity
```

Schema:

```text
reference_set
-------------
set_id
name
description
entity_id      optional
set_type
```

and:

```text
reference_set_asset
-------------------
set_id
asset_id
role
sort_order
```

The role could matter:

```text
canonical
alternate
detail
front
rear
source
deprecated
```

This is analogous to collections in DAM tools: the resources remain independent, but useful groups can be assembled without relocating or duplicating them. ResourceSpace specifically distinguishes collections and asset relationships from filesystem organization, and Lightroom similarly allows ordinary and dynamic collections independent of folders. :chatgpt-content-reference{index="2"}

An image can belong to several sets.

That is a feature, not a problem.

---

## 5. Make prompt descriptors typed data

I would avoid one generic `description` field because you already have at least two fundamentally different kinds of prose:

**Human description**

> Direct-front adult Tsaeytte head reference generated from the September identity lock.

versus **scene-builder prompt material**

> Petite high elf woman with a soft heart-shaped face, vivid violet-purple almond eyes...

Those have different consumers.

A simple descriptor table could look like:

```text
descriptor
----------
descriptor_id
owner_type
owner_id
descriptor_type
text
priority
enabled
```

Where `owner_type` could be:

```text
entity
reference_set
asset
```

and `descriptor_type` could be:

```text
prompt_identity
prompt_visual
prompt_object
prompt_background
selection_notes
human_description
negative_guidance
```

This opens up something particularly useful for Zet: **descriptor inheritance/composition**.

Suppose you choose a particular Tsaeytte image.

The compiler could assemble:

```text
ENTITY:
Tsaeytte base visual descriptor

REFERENCE SET:
Adult Head Reference descriptor

ASSET:
specific visible details of this particular image
```

rather than forcing every image to contain a giant duplicated Tsaeytte description.

That also gives you controlled precedence:

```text
Entity defaults
    ↓
Reference-set specialization
    ↓
Asset-specific description
```

Conceptually, this is similar to your current compiler work: broad truth lives high up; view- or asset-specific information appears closer to the final selection.

---

## 6. Treat "where is this used?" as an explicit relationship

Don't try to infer this permanently from directories.

Have a resource table for things that consume assets:

```text
consumer
--------
consumer_id
consumer_type
name
path
```

Types might be:

```text
scene
costume_template
character_template
prompt_template
job
```

Then:

```text
asset_usage
-----------
asset_id
consumer_id
usage_role
locator
last_seen
```

For example:

```text
asset:
    Tsaeytte Jewelry Reference

consumer:
    Costume_Canonical_Adventure_Gear.md

usage_role:
    object_reference

locator:
    jewelry.reference_image
```

Then you can immediately answer:

> Where is this image used?

or:

> Which images used by active costume templates are marked obsolete?

or:

> Can I safely delete this image?

I would have Zet's compiler/indexer **generate this table automatically** by scanning its own references rather than requiring manual bookkeeping.

`last_seen` is useful because references disappear over time. On an indexing run:

```text
seen this run → current
not seen this run → stale
```

You can then review stale references rather than silently deleting history.

---

## 7. Add one more distinction: physical assets versus logical references

This may be especially valuable for your system.

A template often does not really mean:

> Use image asset `9382701`.

It means:

> Use the current canonical Tsaeytte jewelry reference.

So you could introduce a stable **logical reference**:

```text
reference_key:
tsaeytte.jewelry.canonical
```

which resolves to:

```text
asset_id:
9382701
```

Then your costume template contains:

```yaml
image_ref: tsaeytte.jewelry.canonical
```

instead of a filename or UUID.

If you make a superior jewelry image next month, you change:

```text
tsaeytte.jewelry.canonical
    old asset → new asset
```

once.

Every template using the logical reference automatically picks up the new asset.

You can still track both:

```text
Template → logical reference → current asset
```

This gives you something very close to a symbolic link at the database level.

I suspect this would eliminate quite a bit of library maintenance in Zet.

---

# What I would make "structured"

I wouldn't impose much hierarchy, but I **would impose structure wherever a field affects behavior or frequent filtering**.

| Concept | Representation |
|---|---|
| Tsaeytte | Entity |
| Character | Entity type |
| Canonical Adventure Gear | Entity |
| FRONT | Controlled facet/tag |
| full body | Controlled facet/tag |
| angry | Tag |
| canonical | Status or controlled facet |
| several Tsaeytte head images | Reference Set |
| actual PNG | Asset |
| prompt prose | Descriptor |
| costume uses PNG | Usage relationship |
| "current jewelry reference" | Logical reference |
| miscellaneous visual property | Free tag |

A good rule is:

> **If Zet needs to understand what the value means, don't make it an unstructured tag.**

Tags answer:

> What attributes does this have?

Entities answer:

> What thing is this?

Reference sets answer:

> Which images belong together for this purpose?

Descriptors answer:

> What should Zet say about it?

Usage answers:

> Who depends on it?

---

# Filtering then becomes very natural

Instead of browsing:

```text
Characters
  Tsaeytte
    Adult
      Costume
        Adventure Gear
           ...
```

the UI begins with a search/result grid and facets.

For example:

```text
Entity:      Tsaeytte
Purpose:     Identity Reference
Framing:     Head
View:        FRONT
Status:      Approved
```

You might get three images.

Or:

```text
Entity:      Utility Tusk
```

and immediately see every image involving the tusk, grouped into:

```text
Shape References
Tsaeytte Holding Tusk
Tusk Details
Historical / Obsolete
```

This is essentially **faceted search**, which is where metadata catalogs become much easier to use than folder trees. Lightroom's catalog, for example, allows filters by keyword and many other metadata dimensions, and its Smart Collections dynamically assemble assets from those rules. :chatgpt-content-reference{index="3"}

---

# I would keep the initial schema fairly small

Something like this would probably be enough for the first clean break:

```text
Asset
Entity
AssetEntity

Tag
AssetTag

ReferenceSet
ReferenceSetAsset

Descriptor

LogicalReference

Consumer
AssetUsage

AssetRelation
```

`AssetRelation` is useful for provenance:

```text
derived_from
cropped_from
edited_from
transparent_version_of
generated_from
replacement_for
```

That gives you a lightweight graph without adopting an actual graph database. SQLite/PostgreSQL relational tables are completely adequate for this.

In fact, **SQLite seems particularly well suited to Zet** unless you're already using some other database. This is highly relational data, the scale is modest, local operation matters, and SQLite gives you proper indexes, foreign keys, full-text search, transactions, and essentially zero administration.

---

## A concrete Tsaeytte example

Imagine this image:

```text
tsaeytte_adventure_front.png
```

Its database representation might effectively say:

```text
ASSET
  id: A-1042
  status: approved

ENTITIES
  Tsaeytte              primary_subject
  Canonical Adventure Gear   costume
  Tsaeytte Jewelry      worn_object

REFERENCE SETS
  Tsaeytte Adult — Canonical Adventure Gear
  Tsaeytte Adult — Full Body References

FACETS
  view:front
  framing:full_body
  purpose:costume_reference
  background:neutral

DESCRIPTORS
  prompt_visual:
    "Direct-front full-body reference ..."

  selection_notes:
    "Best current reference for skirt shape."

LOGICAL REFERENCES
  tsaeytte.costume.adventure.front -> A-1042

USAGES
  Costume_Canonical_Adventure_Gear.md
  Scene_SpireEntrance.md
```

Nothing in that model depends on where the PNG happens to live.

That is the central architectural change I would make.

The parts of other DAM systems worth borrowing are therefore **metadata instead of folder taxonomy, controlled vocabularies for frequently filtered concepts, free keywords for the long tail, collections for purposeful groups, explicit relationships among related assets, and dynamic/saved searches**. :chatgpt-content-reference{index="4"}

For Zet specifically, I'd add the two pieces generic DAM systems usually don't have: **typed prompt descriptors** and **logical references that point to the current preferred asset**. Those are the pieces that turn this from an image catalog into infrastructure for your compiler and scene-builder.

## Base Pipeline Images

Base pipeline images, Body-Reference, Head-Image,, Character-Assembly, and Costume-Dressing are only in the library when they are Locked.

Candidate images in the pipelines are NOT in the library and are not selectable for reference outside of the pipeline process via the library.
