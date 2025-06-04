from llama_index.readers.file import DocxReader, PDFReader
from langchain_core.documents import Document
from typing import List

class PdfFileUtil:
    def __init__(self):
        self.reader = PDFReader()

    def extract_documents_from(self, pdf_path) -> List[Document]:
        documents = self.reader.load_data(pdf_path)
        for i in range(len(documents)):
            documents[i] = documents[i].to_langchain_format() # List[Document]， LlamaIndex
            documents[i].metadata = {key: value for key, value in documents[i].metadata.items() if value is not None}

        return documents