class FakeEncoding:
    def encode(self, text):
        return text.encode('utf-8') if isinstance(text, str) else text

def get_encoding(name="o200k_base"):
    return FakeEncoding()
