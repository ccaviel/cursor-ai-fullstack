from setuptools import setup, find_packages

setup(
    name="rag_module",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "langchain>=0.1.0",
        "llama-index>=0.9.8",
        "openai>=1.1.0",
        "chromadb>=0.4.18",
        "python-dotenv==1.0.0",
        "tiktoken>=0.5.2",
        "numpy>=1.24.3",
        "pandas>=2.0.3"
    ]
)
