# ideas — the idea records

An idea arrives freeform, in the owner's words, and is recorded the
hour it arrives: verbatim, dated, with a disposition. It hardens into
a ruling through the register (`tools/decisions.py`, a `D-` row with
the owner's words as evidence), and is executed through work orders
under that ruling's authority. The chain is petition → statute → writ;
this directory is the petitions, and the system bootstraps by recording
the idea that called for it.

## The record

One file per idea, `I-NNN-<slug>.md`, numbered in arrival order and
never renumbered. Shape:

```
# I-NNN — <title in a phrase>

- recorded: <date>, <where in the conversation it arrived>
- source: owner, verbatim below
- disposition: open | ratified (D-…) | superseded by I-… | spent

## In the owner's words
> the words, verbatim, elided only with […] where a name may not stand in this tree

## What was heard
the conductor's reading: what it means, what it changes, what it must reconcile with

## Standing facts it must reconcile with
measured facts, each with its command, stamped
```

Rules: the owner's words are never paraphrased in the quote block; the
reading is the conductor's and says so; an idea is never edited after
recording except its disposition line, which is amended by commit; a
superseded idea points forward and stays.

The House holds 61 records in this form; none of them crosses. This
project's records begin at I-001.
