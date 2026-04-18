FROM python:3.10 AS builder

WORKDIR /usr/src/app

RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"

RUN pip install --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir .


FROM python:3.10 AS test_runner
WORKDIR /tmp
COPY --from=builder /venv /venv
COPY --from=builder /usr/src/app/tests tests
ENV PATH=/venv/bin:$PATH

# install test dependencies
RUN pip install pytest

# run tests
RUN pytest tests


FROM python:3.10 AS service
WORKDIR /usr/src/app
COPY --from=test_runner /venv /venv
ENV PATH=/venv/bin:$PATH

EXPOSE 8080

CMD ["uvicorn", "ai_travel_planner.main:app", "--host", "0.0.0.0", "--port", "8080"]
