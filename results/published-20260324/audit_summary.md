# Published Result Set Audit

- raw master rows: 2917
- cleaned master rows: 1839
- raw issue/title rows: 5154
- cleaned issue/title rows: 2597
- dropped noisy rows: 2557
- unresolved issues: 35

Cleaning rules used:
- keep all `vollversion-fullversion` rows
- drop obvious issue-code/track rows like `CBS0100 (Track 01)`
- drop obvious UI/settings/manual/software noise
- keep multi-word titles that survive the blacklist
- keep title-cased single-word titles only when they are not obvious noise

Publishable tier:
- keeps all `vollversion-fullversion` rows
- keeps only stronger `disc-metadata-value` rows
- excludes manifest-only and command-only rows from the publishable tier

Original raw data remains untouched in the source snapshot.
