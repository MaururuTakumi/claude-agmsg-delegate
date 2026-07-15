PYTHON ?= python3

.PHONY: test check install dry-run

test:
	$(PYTHON) -m py_compile scripts/delegate_claude.py tests/test_delegate_claude.py
	$(PYTHON) tests/test_delegate_claude.py -v
	bash -n install.sh
	./install.sh --help >/dev/null

check: test
	@if rg -n -i '/Users/|/tmp/|gh[pousr]_[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY|api[_-]?key[[:space:]]*[:=][[:space:]]*[^<]' \
		--glob '!Makefile' --glob '!tests/test_delegate_claude.py' --glob '!evals/**' .; then \
		echo 'check: possible sensitive or machine-local content found' >&2; exit 1; \
	else \
		echo 'check: no machine-local paths or likely secrets found'; \
	fi

dry-run:
	./install.sh --dry-run

install:
	./install.sh
