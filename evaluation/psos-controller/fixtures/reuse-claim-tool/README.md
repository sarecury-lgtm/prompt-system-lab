# Comment claim extractor fixture

`tools/comment_claim_extractor.py` is a deliberately small first-pass filter. It does not prove that a line is true and does not perfectly separate fact from opinion. It only selects lines containing markers commonly associated with externally verifiable claims.

Example:

```bash
python tools/comment_claim_extractor.py sample_comments.txt
```
