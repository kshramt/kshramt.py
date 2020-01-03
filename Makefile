# Constants
DEPS :=

export MY_PYTHON ?= venv/bin/python3
PYTHON := $(MY_PYTHON)

# Configurations
.SUFFIXES:
.DELETE_ON_ERROR:
.SECONDARY:
.ONESHELL:
export SHELL := /bin/bash
export SHELLOPTS := pipefail:errexit:nounset:noclobber

# Tasks
.PHONY: all deps check build
all: deps
deps: $(DEPS:%=dep/%.updated)
check: test/kshramt.py.tested

build: deps
	readonly tmp_dir="$$(mktemp -d)"
	git ls-files | xargs -I{} echo cp --parents ./{} "$$tmp_dir"
	git ls-files | xargs -I{} cp --parents ./{} "$$tmp_dir"
	mkdir -p "$${tmp_dir}"/eq
	cd "$$tmp_dir"
	$(PYTHON) setup.py sdist
	mkdir -p $(CURDIR)/dist/
	mv -f dist/* $(CURDIR)/dist/
	rm -fr "$${tmp_dir}"

# Files
test/kshramt.py.tested: kshramt.py
	mkdir -p $(@D)
	$(PYTHON) kshramt.py
	touch $@

# Rules

define DEPS_RULE_TEMPLATE =
dep/$(1)/%: | dep/$(1).updated ;
endef
$(foreach f,$(DEPS),$(eval $(call DEPS_RULE_TEMPLATE,$(f))))

dep/%.updated: config/dep/%.ref dep/%.synced
	cd $(@D)/$*
	git fetch origin
	git merge "$$(cat ../../$<)"
	cd -
	if [[ -r dep/$*/Makefile ]]; then
	   $(MAKE) -C dep/$*
	fi
	touch $@

dep/%.synced: config/dep/%.uri | dep/%
	cd $(@D)/$*
	git remote rm origin
	git remote add origin "$$(cat ../../$<)"
	cd -
	touch $@

$(DEPS:%=dep/%): dep/%:
	git init $@
	cd $@
	git remote add origin "$$(cat ../../config/dep/$*.uri)"
