"""Small used provider boundary: refresh(stop), snapshot(nonce), close().

Only the existing Codex implementation exists. Future providers must produce
the verified wire schema and require explicit device compatibility work.
"""
def create_source(provider='codex'):
    if provider != 'codex':
        raise ValueError('Only Codex is supported')
    from monitor import Source
    return Source([])
