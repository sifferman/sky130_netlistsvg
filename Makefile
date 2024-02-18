
DOWNLOAD := download
JSON := json
SVG := svg

REPO := efabless/skywater-pdk-libs-sky130_fd_sc_hd

${DOWNLOAD}/%.spice:
	mkdir -p $(dir $@)
	wget -O $@ https://raw.githubusercontent.com/${REPO}/master/$*.spice

${JSON}/%.json: ${DOWNLOAD}/%.spice
	mkdir -p $(dir $@)
	./spice2json.py $< > $@

${SVG}/%.svg: ${JSON}/%.json
	mkdir -p $(dir $@)
	netlistsvg $< -o $@
	sed -i -E 's@(<svg[^>]*>)@\1<rect width="100%" height="100%" fill="white"/>@g' "$@"
