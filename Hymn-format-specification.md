## The `.hymn` format specification

This is the contract every script reads and writes.

All keys are optional except `number` and `title`. `number` must be unique; 
the filename is the zero-padded number (`042.hymn`).

The purpose for the two category fields is that SoftProjector has a hard-coded
set of category fields which hymns have been mapped to. The Reformation Hymnal
has its own set of categories which are tracked for those deliverable formats
which may support them.

### Example (`source/001.hymn`)

```
---
number: 26
title: We Praise Thee, O God
common_title: Revive Us Again
author: William P. Mackay
composer: John J. Husband
sp_category: "1"                       # SoftProjector's built-in category
topic: Adoration                       # the printed hymnal's own subject index
notes: ""                              # editorial notes, never projected
---

[verse 1]
Before Jehovah’s awful throne,
Ye nations bow with sacred joy;
Know that the Lord is God alone;
He can create, and He destroy.

[verse 2]
His sovereign power, without our aid,
Made us of clay, and formed us men;
And when like wandering sheep we strayed,
He brought us to His fold again.

[verse 3]
We’ll crowd His gates with thankful songs,
High as the heavens our voices raise;
And earth, with her ten thousand tongues,
Shall fill His courts with sounding praise.

[verse 4]
Wide as the world is His command,
Vast as Eternity His love;
Firm as a rock His truth shall stand,
When rolling years shall cease to move.]
