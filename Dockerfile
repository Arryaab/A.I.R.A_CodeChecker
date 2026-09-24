FROM python:3.12-slim
# Install only pytest
RUN pip install --no-cache-dir pytest
# Set working directory
WORKDIR /workspace
# Security: run as non-root user
RUN useradd -m -s /bin/bash aegis
USER aegis
# Default command runs pytest
CMD ["python", "-m", "pytest", "-v", "--tb=short", "--color=no", "-p", "no:cacheprovider"]
