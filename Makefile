.PHONY: build sps freeshow fetch enrich diff check test clean extract inspect

build: sps freeshow          ## build everything into dist/

sps:                         ## compile source/*.hymn -> dist/ReformationHymnal.sps
	python -m build.to_softprojector

freeshow:                    ## compile source/*.hymn -> dist/ReformationHymnal.project
	python -m build.to_freeshow

fetch:                       ## (Phase 3) download online hymnal JSON -> reference/rh_online.json
	python -m build.fetch_online

enrich:                      ## (Phase 3) enrich source/*.hymn with topic/title/tune from online JSON
	python -m build.enrich_online

diff:                        ## (Phase 3) compare source lyrics vs online JSON -> dist/diff.html
	python -m build.diff_online

apply:                       ## (Phase 3) apply online lyrics to source/*.hymn (with patches)
	python -m build.apply_online

check:                       ## cross-check source against reference PDF (deprecated)
	python -m build.check_pdf

extract:                     ## (Phase 1) extract reference/original.sps -> source/*.hymn
	python -m build.extract_sps --db reference/original.sps --out source/

inspect:                     ## (Phase 1) inspect .sps schema and sample output
	python -m build.extract_sps --db reference/original.sps --inspect

test:                        ## run test suite
	python -m pytest

clean:                       ## delete all generated output
	find dist/ -mindepth 1 -delete 2>/dev/null; true
