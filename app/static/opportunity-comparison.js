(function initializeOpportunityComparison(globalObject) {
  "use strict";

  const map = globalObject.edgeOpportunityMap;
  const $node = (tag, className, content) => {
    const element = globalObject.document.createElement(tag);
    if (className) element.className = className;
    if (content !== undefined) element.textContent = content;
    return element;
  };
  const parseTime = (value) => value ? new Date(value).getTime() : Number.NaN;
  const exactTime = (value) => value
    ? (globalObject.formatOperatorTimestampUtcMinus4?.(value) || new Date(value).toLocaleString())
    : "Unavailable";
  const exactPrice = (value) => {
    const numeric = Number(value);
    return Number.isFinite(numeric)
      ? numeric.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })
      : "Unavailable";
  };
  const eventId = (item) => map.eventIdentity(item);

  function cursorIndexAtOrBefore(cursors, value) {
    const timestamp = parseTime(value);
    return Math.max(0, (cursors || []).reduce(
      (current, item, index) => parseTime(item) <= timestamp ? index : current,
      0,
    ));
  }

  function detailCursors(detail) {
    return map.collectReplayCursors(detail).filter((value) => Number.isFinite(parseTime(value)));
  }

  function unifiedCheckpoints(details) {
    const checkpoints = [];
    (details || []).forEach((detail) => {
      map.timelineRows(detail).forEach((item) => checkpoints.push({
        at: item.known_at,
        symbol: detail.symbol,
        event: item,
      }));
    });
    const snapshot = details?.[0]?.as_of;
    if (snapshot) checkpoints.push({ at: snapshot, symbol: "Both", event: null });
    const seen = new Set();
    return checkpoints
      .filter((item) => Number.isFinite(parseTime(item.at)))
      .sort((left, right) => parseTime(left.at) - parseTime(right.at) || left.symbol.localeCompare(right.symbol))
      .filter((item) => {
        const key = `${item.at}:${item.symbol}:${eventId(item.event)}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
  }

  function lastLifecycle(detail) {
    return (detail.mrz_lifecycles || []).at(-1) || null;
  }

  function latestStructuralEvent(detail) {
    return map.timelineRows(detail)
      .slice()
      .sort((left, right) => parseTime(right.known_at) - parseTime(left.known_at))[0] || null;
  }

  function nearMissStatus(detail) {
    const episodes = detail.near_miss_events || [];
    if (!episodes.length) return "No known Near Miss";
    const active = episodes.filter((item) => !item.ended_at || parseTime(item.ended_at) > parseTime(detail.as_known_at));
    return active.length ? `Active (${active.length})` : `Historical (${episodes.length})`;
  }

  function comparisonFacts(detail) {
    const mrz = lastLifecycle(detail);
    const latest = latestStructuralEvent(detail);
    return [
      ["Latest observed IPDA location", detail.latest_ipda_location || "Unavailable"],
      ["Authoritative MRZ route", mrz?.route || "Unavailable"],
      ["Active MRZ bounds", mrz ? `${exactPrice(mrz.lower_bound)}–${exactPrice(mrz.upper_bound)}` : "Unavailable"],
      ["Canonical observations", `${(detail.observations || []).length} observations`],
      ["Latest structural change", latest ? `${latest.event_type} · ${exactTime(latest.known_at)}` : "Unavailable"],
      ["Near Miss status", nearMissStatus(detail)],
      ["Next condition to monitor", detail.assessment?.next_condition || "Unavailable"],
    ];
  }

  function structuralStatements(details) {
    const [left, right] = details;
    const statements = [];
    const eventTime = (detail, source) => {
      const items = source(detail).filter((item) => item.known_at);
      return items.length ? items.map((item) => parseTime(item.known_at)).sort((a, b) => a - b)[0] : null;
    };
    const leadership = [
      ["Near Miss", (detail) => detail.near_miss_events || []],
      ["MRZ activation", (detail) => (detail.mrz_lifecycles || []).filter((item) => item.event_type === "MRZ_ACTIVATED")],
    ];
    leadership.forEach(([label, source]) => {
      const leftAt = eventTime(left, source);
      const rightAt = eventTime(right, source);
      if (leftAt && rightAt && leftAt !== rightAt) {
        const earlier = leftAt < rightAt ? left : right;
        statements.push(`${earlier.symbol} recorded the earlier ${label} event. This describes event order, not trade quality.`);
      }
    });
    if (!statements.length) statements.push("No comparable structural divergence is available at the selected replay cutoffs.");
    return statements;
  }

  function renderSummary(details) {
    const panel = $node("section", "opportunity-comparison-summary panel");
    const header = $node("header", "opportunity-panel-heading");
    header.append($node("div", "", "Relative Structural Comparison"), $node("span", "", "Factual evidence · no score or signal"));
    panel.append(header);
    const tableWrap = $node("div", "comparison-summary-table-wrap");
    const table = $node("table", "comparison-summary-table");
    const head = $node("thead", "");
    head.innerHTML = `<tr><th>Dimension</th><th>${details[0].symbol}</th><th>${details[1].symbol}</th></tr>`;
    const facts = details.map(comparisonFacts);
    const body = $node("tbody", "");
    facts[0].forEach(([label, value], index) => {
      const row = $node("tr", "");
      row.append($node("th", "", label), $node("td", "", value), $node("td", "", facts[1][index][1]));
      body.append(row);
    });
    table.append(head, body); tableWrap.append(table); panel.append(tableWrap);
    const interpretation = $node("div", "comparison-interpretation");
    interpretation.append($node("strong", "", "Evidence-based interpretation"));
    const list = $node("ul", "");
    structuralStatements(details).forEach((statement) => list.append($node("li", "", statement)));
    interpretation.append(list); panel.append(interpretation);
    return panel;
  }

  function renderSelector(label, value, members, onChange) {
    const wrapper = $node("label", "comparison-symbol-selector");
    wrapper.append($node("span", "", label));
    const select = $node("select", "");
    members.forEach((symbol) => {
      const option = $node("option", "", symbol);
      option.value = symbol; option.selected = symbol === value; select.append(option);
    });
    select.addEventListener("change", () => onChange(select.value));
    wrapper.append(select); return wrapper;
  }

  function renderComparison(target, config) {
    const members = [...new Set(config.members || [])];
    const initialA = members.includes(config.symbolA) ? config.symbolA : members[0];
    const initialB = members.includes(config.symbolB) && config.symbolB !== initialA
      ? config.symbolB
      : members.find((symbol) => symbol !== initialA);
    const state = {
      symbolA: initialA,
      symbolB: initialB,
      rangeDays: 0,
      synchronised: true,
      replayA: null,
      replayB: null,
      details: null,
      fullDetails: null,
      checkpoints: [],
      checkpointIndex: 0,
      selected: null,
      playing: false,
      playTimer: null,
      sliderTimer: null,
      maximized: false,
      requestId: 0,
    };

    if (!initialA || !initialB) {
      target.replaceChildren($node("section", "panel opportunity-error", "At least two group members are required for comparison."));
      return Promise.resolve();
    }
    if (initialA !== config.symbolA || initialB !== config.symbolB) {
      config.onSelectionChange?.(initialA, initialB);
    }

    const comparisonUrl = (latest = false) => {
      const params = new URLSearchParams({ group_id: config.groupId, symbol_a: state.symbolA, symbol_b: state.symbolB });
      if (!latest) {
        if (state.synchronised && state.replayA) params.set("as_known_at", state.replayA);
        if (!state.synchronised) {
          if (state.replayA) params.set("as_known_at_a", state.replayA);
          if (state.replayB) params.set("as_known_at_b", state.replayB);
        }
      }
      return `/api/opportunities/compare?${params}`;
    };

    const load = async ({ latest = false } = {}) => {
      const requestId = ++state.requestId;
      target.setAttribute("aria-busy", "true");
      const response = await globalObject.fetch(comparisonUrl(latest), { cache: "no-store" });
      if (!response.ok) throw new Error("Opportunity comparison is unavailable.");
      const payload = await response.json();
      if (requestId !== state.requestId) return;
      state.details = payload.details;
      if (latest || !state.fullDetails) {
        state.fullDetails = payload.details;
        state.checkpoints = unifiedCheckpoints(payload.details);
        state.checkpointIndex = Math.max(0, state.checkpoints.length - 1);
        state.replayA = payload.details[0].as_known_at;
        state.replayB = payload.details[1].as_known_at;
      }
      target.removeAttribute("aria-busy");
      render();
    };

    const selectSymbols = (nextA, nextB) => {
      if (nextA === nextB) {
        if (nextA === state.symbolA) nextB = members.find((symbol) => symbol !== nextA);
        else nextA = members.find((symbol) => symbol !== nextB);
      }
      state.symbolA = nextA; state.symbolB = nextB;
      state.fullDetails = null; state.selected = null; state.playing = false;
      globalObject.clearTimeout(state.playTimer);
      config.onSelectionChange?.(nextA, nextB);
      target.replaceChildren($node("section", "panel opportunity-loading", `Loading ${nextA} and ${nextB}…`));
      load({ latest: true }).catch(showError);
    };

    const showError = (error) => {
      target.removeAttribute("aria-busy");
      target.replaceChildren($node("section", "panel opportunity-error", error.message));
    };

    const moveShared = (index) => {
      const bounded = Math.max(0, Math.min(state.checkpoints.length - 1, index));
      state.checkpointIndex = bounded;
      state.replayA = state.checkpoints[bounded].at;
      state.replayB = state.replayA;
      load().catch(showError);
    };

    const renderReplaySlider = (label, value, cursors, onCommit) => {
      const row = $node("label", "comparison-independent-replay");
      row.append($node("span", "", label));
      const input = $node("input", ""); input.type = "range"; input.step = "1";
      input.min = "0"; input.max = String(Math.max(0, cursors.length - 1));
      input.value = String(cursorIndexAtOrBefore(cursors, value)); input.setAttribute("aria-label", `${label} replay cutoff`);
      const output = $node("output", "", exactTime(value));
      input.addEventListener("input", () => { output.textContent = exactTime(cursors[Number(input.value)]); });
      input.addEventListener("change", () => onCommit(cursors[Number(input.value)]));
      row.append(input, output); return row;
    };

    const render = () => {
      const details = state.details;
      if (!details) return;
      target.replaceChildren();
      const workspace = $node("section", "opportunity-comparison-workspace");
      workspace.classList.toggle("maximized", state.maximized);
      const header = $node("header", "comparison-header");
      const identity = $node("div", "comparison-heading");
      identity.append($node("p", "", "GROUP RADAR · COMPARISON"), $node("h2", "", `${config.groupName} — Opportunity Comparison`), $node("span", "", "Actual time · independent actual-price scales · canonical evidence"));
      const back = $node("button", "quiet-button", "← Back to Group"); back.type = "button"; back.addEventListener("click", config.onBack || (() => {}));
      header.append(identity, back); workspace.append(header);

      const toolbar = $node("section", "comparison-toolbar panel");
      const selectors = $node("div", "comparison-selectors");
      selectors.append(
        renderSelector("Symbol A", state.symbolA, members, (value) => selectSymbols(value, state.symbolB)),
        renderSelector("Symbol B", state.symbolB, members, (value) => selectSymbols(state.symbolA, value)),
      );
      const ranges = $node("div", "opportunity-range-controls comparison-ranges");
      [[0, "All"], [90, "90D"], [30, "30D"]].forEach(([days, label]) => {
        const button = $node("button", "", label); button.type = "button";
        button.setAttribute("aria-pressed", String(state.rangeDays === days));
        button.addEventListener("click", () => { state.rangeDays = days; render(); }); ranges.append(button);
      });
      const maximize = $node("button", "opportunity-maximize-button", state.maximized ? "Restore" : "Maximize");
      maximize.type = "button"; maximize.addEventListener("click", () => {
        state.maximized = !state.maximized;
        globalObject.document.body.classList.toggle("opportunity-map-maximized", state.maximized);
        render();
      });
      toolbar.append(selectors, ranges, maximize); workspace.append(toolbar);

      const replay = $node("section", "comparison-replay panel");
      const replayHeader = $node("header", "opportunity-panel-heading");
      const newlyReached = state.checkpoints[state.checkpointIndex];
      const replayIdentity = $node("div", "");
      replayIdentity.append($node("strong", "", "Historical Replay — As Known At"), $node("small", "", newlyReached?.event ? `${newlyReached.symbol} generated the reached ${newlyReached.event.event_type} checkpoint` : "Unified canonical evidence checkpoints"));
      const replayActions = $node("div", "comparison-replay-actions");
      const sync = $node("label", "comparison-sync");
      const checkbox = $node("input", ""); checkbox.type = "checkbox"; checkbox.checked = state.synchronised;
      checkbox.setAttribute("aria-label", "Sync Replay");
      checkbox.addEventListener("change", () => {
        state.synchronised = checkbox.checked;
        if (state.synchronised) state.replayB = state.replayA;
        load().catch(showError);
      });
      sync.append(checkbox, $node("span", "", "Sync Replay"));
      const controls = $node("div", "opportunity-replay-controls");
      const previous = $node("button", "quiet-button", "Previous"); previous.type = "button"; previous.disabled = !state.synchronised; previous.addEventListener("click", () => moveShared(state.checkpointIndex - 1));
      const play = $node("button", "primary-button", state.playing ? "Pause" : "Play"); play.type = "button"; play.disabled = !state.synchronised;
      play.addEventListener("click", () => {
        state.playing = !state.playing;
        globalObject.clearTimeout(state.playTimer);
        if (!state.playing) { render(); return; }
        const advance = () => {
          if (!state.playing) return;
          const nextIndex = state.checkpointIndex >= state.checkpoints.length - 1 ? 0 : state.checkpointIndex + 1;
          state.checkpointIndex = nextIndex; state.replayA = state.checkpoints[nextIndex].at; state.replayB = state.replayA;
          load().then(() => { if (state.playing) state.playTimer = globalObject.setTimeout(advance, 900); }).catch(showError);
        };
        advance();
      });
      const next = $node("button", "quiet-button", "Next"); next.type = "button"; next.disabled = !state.synchronised; next.addEventListener("click", () => moveShared(state.checkpointIndex + 1));
      const latest = $node("button", "quiet-button", "Latest"); latest.type = "button"; latest.addEventListener("click", () => {
        if (state.synchronised) moveShared(state.checkpoints.length - 1);
        else { state.replayA = state.fullDetails[0].as_known_at; state.replayB = state.fullDetails[1].as_known_at; load().catch(showError); }
      });
      controls.append(previous, play, next, latest);
      replayActions.append(sync, controls);
      replayHeader.append(replayIdentity, replayActions); replay.append(replayHeader);
      if (state.synchronised) {
        const sliderRow = $node("div", "opportunity-replay-slider-row");
        const slider = $node("input", "opportunity-replay-slider"); slider.type = "range"; slider.step = "1";
        slider.min = "0"; slider.max = String(Math.max(0, state.checkpoints.length - 1)); slider.value = String(state.checkpointIndex);
        slider.setAttribute("aria-label", "Synchronized historical replay timestamp");
        const output = $node("output", "opportunity-replay-selected", exactTime(state.replayA));
        const commit = () => {
          state.checkpointIndex = Math.max(0, Math.min(state.checkpoints.length - 1, Number(slider.value)));
          state.replayA = state.checkpoints[state.checkpointIndex].at; state.replayB = state.replayA; load().catch(showError);
        };
        slider.addEventListener("input", () => {
          output.textContent = exactTime(state.checkpoints[Number(slider.value)].at);
          globalObject.clearTimeout(state.sliderTimer); state.sliderTimer = globalObject.setTimeout(commit, 160);
        });
        slider.addEventListener("change", () => { globalObject.clearTimeout(state.sliderTimer); commit(); });
        sliderRow.append(slider, output); replay.append(sliderRow);
      } else {
        const independent = $node("div", "comparison-independent-replays");
        independent.append(
          renderReplaySlider(state.symbolA, state.replayA, detailCursors(state.fullDetails[0]), (value) => { state.replayA = value; load().catch(showError); }),
          renderReplaySlider(state.symbolB, state.replayB, detailCursors(state.fullDetails[1]), (value) => { state.replayB = value; load().catch(showError); }),
        );
        replay.append(independent);
      }
      replay.append($node("p", "opportunity-replay-note", state.synchronised
        ? `Both maps show evidence known by ${exactTime(state.replayA)}. Event time and knowledge time remain separate.`
        : `${state.symbolA}: ${exactTime(state.replayA)} · ${state.symbolB}: ${exactTime(state.replayB)}. The chronological X-axis remains shared.`));
      workspace.append(replay);

      const bounds = map.comparisonTimeBounds(state.fullDetails, state.rangeDays);
      const charts = $node("div", "comparison-chart-grid");
      const selectedDetails = $node("section", "opportunity-selected-event comparison-selected-event panel");
      const selectEvent = (symbol, item) => {
        state.selected = { symbol, item: { ...item, symbol } };
        render();
      };
      details.forEach((detail) => {
        const panel = $node("section", "comparison-chart panel");
        const chartHeader = $node("header", "opportunity-panel-heading");
        const chartActions = $node("div", "comparison-chart-actions");
        chartActions.append(
          $node("span", "", `Cutoff ${exactTime(detail.as_known_at)}`),
          map.renderCanonicalEvidenceLink(detail, {
            groupId: config.groupId,
            window: config.window,
            returnUrl: config.returnUrl,
          }),
        );
        chartHeader.append($node("div", "", `${detail.symbol} — Opportunity Map`), chartActions); panel.append(chartHeader);
        const scroll = $node("div", "opportunity-chart-scroll");
        const canvas = $node("canvas", "opportunity-map-canvas comparison-map-canvas"); canvas.width = 920; canvas.height = 340; canvas.tabIndex = 0; canvas.setAttribute("aria-label", `Time-price opportunity map for ${detail.symbol}`);
        scroll.append(canvas); panel.append(scroll);
        if (!map.timelineRows(detail).length) panel.append($node("p", "comparison-empty-evidence", "No evidence available at this timestamp"));
        panel.append(map.renderLegend()); charts.append(panel);
        globalObject.requestAnimationFrame(() => map.drawChart(
          canvas,
          detail,
          state.rangeDays,
          state.selected?.symbol === detail.symbol ? eventId(state.selected.item) : null,
          (item) => selectEvent(detail.symbol, item),
          { timeBounds: bounds, timeCursor: state.selected?.item?.effective_at },
        ));
      });
      workspace.append(charts);
      map.renderEventDetails(selectedDetails, state.selected?.item || null, {
        onClose: state.selected ? () => { state.selected = null; render(); } : null,
      });
      workspace.append(selectedDetails, renderSummary(details)); target.append(workspace);
    };

    const escapeHandler = (event) => {
      if (event.key === "Escape" && state.maximized) {
        state.maximized = false;
        globalObject.document.body.classList.remove("opportunity-map-maximized");
        render();
      }
    };
    globalObject.document.addEventListener("keydown", escapeHandler);
    target.replaceChildren($node("section", "panel opportunity-loading", `Loading ${initialA} and ${initialB}…`));
    return load({ latest: true }).catch(showError);
  }

  globalObject.edgeOpportunityComparison = { cursorIndexAtOrBefore, renderComparison, structuralStatements, unifiedCheckpoints };
})(window);
