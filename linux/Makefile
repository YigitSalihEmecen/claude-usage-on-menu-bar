# Claude Usage for Linux.
#
#   make run                     run from this checkout
#   make test                    run the test suite (UI tests need a display; see CONTRIBUTING.md)
#   make lint                    ruff check and format check
#   sudo make install            install under /usr/local
#   make install PREFIX=~/.local install for the current user only
#   sudo make uninstall          remove what `make install` put there
#   make deb                     build dist/claude-usage_<version>_all.deb
#   make dist                    build dist/claude-usage-linux-<version>.tar.gz

NAME      := claude-usage
APP_ID    := io.github.YigitSalihEmecen.ClaudeUsage
VERSION   := $(shell sed -n 's/^__version__ = "\(.*\)"/\1/p' claude_usage/__init__.py)

PREFIX    ?= /usr/local
DESTDIR   ?=
BINDIR    := $(PREFIX)/bin
LIBDIR    := $(PREFIX)/share/$(NAME)
DATADIR   := $(PREFIX)/share

# Pin timestamps so the same source builds the same archive.
SOURCE_DATE_EPOCH ?= $(shell git log -1 --format=%ct 2>/dev/null || date +%s)
export SOURCE_DATE_EPOCH

PYTHON    ?= python3

.PHONY: run test lint format install uninstall refresh-caches deb dist clean version

run:
	$(PYTHON) -m claude_usage

test:
	$(PYTHON) -m unittest discover -s tests -t . -v

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .
	ruff check --fix .

version:
	@echo $(VERSION)

install:
	install -d $(DESTDIR)$(BINDIR) $(DESTDIR)$(LIBDIR)/claude_usage/ui
	install -m 644 claude_usage/*.py $(DESTDIR)$(LIBDIR)/claude_usage/
	install -m 644 claude_usage/ui/*.py $(DESTDIR)$(LIBDIR)/claude_usage/ui/
	sed 's|@LIBDIR@|$(LIBDIR)|' packaging/$(NAME).in > $(DESTDIR)$(BINDIR)/$(NAME)
	chmod 755 $(DESTDIR)$(BINDIR)/$(NAME)
	install -Dm 644 packaging/$(APP_ID).desktop $(DESTDIR)$(DATADIR)/applications/$(APP_ID).desktop
	install -Dm 644 packaging/$(APP_ID).metainfo.xml $(DESTDIR)$(DATADIR)/metainfo/$(APP_ID).metainfo.xml
	install -Dm 644 packaging/icons/hicolor/scalable/apps/$(APP_ID).svg \
		$(DESTDIR)$(DATADIR)/icons/hicolor/scalable/apps/$(APP_ID).svg
	install -d $(DESTDIR)$(DATADIR)/man/man1
	sed 's|@VERSION@|$(VERSION)|' packaging/$(NAME).1 > $(DESTDIR)$(DATADIR)/man/man1/$(NAME).1
	chmod 644 $(DESTDIR)$(DATADIR)/man/man1/$(NAME).1
	$(MAKE) -s refresh-caches

uninstall:
	rm -rf $(DESTDIR)$(LIBDIR)
	rm -f $(DESTDIR)$(BINDIR)/$(NAME)
	rm -f $(DESTDIR)$(DATADIR)/applications/$(APP_ID).desktop
	rm -f $(DESTDIR)$(DATADIR)/metainfo/$(APP_ID).metainfo.xml
	rm -f $(DESTDIR)$(DATADIR)/icons/hicolor/scalable/apps/$(APP_ID).svg
	rm -f $(DESTDIR)$(DATADIR)/man/man1/$(NAME).1
	$(MAKE) -s refresh-caches

# Packages refresh these through dpkg triggers; a manual install does it here.
refresh-caches:
ifeq ($(DESTDIR),)
	-gtk-update-icon-cache -q -t -f $(DATADIR)/icons/hicolor 2>/dev/null
	-update-desktop-database -q $(DATADIR)/applications 2>/dev/null
endif

deb:
	scripts/build-deb.sh

dist:
	scripts/build-tarball.sh

clean:
	rm -rf dist build .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
