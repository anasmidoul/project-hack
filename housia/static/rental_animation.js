function mountRentalAnimation(section) {
  const button = section.querySelector('.rental-animation__play');
  const player = section.querySelector('.rental-animation__player');
  const board = section.querySelector('.rental-animation__board');
  const caption = section.querySelector('.rental-animation__caption');
  const progress = section.querySelector('.rental-animation__progress');
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const enquiries = [...board.querySelectorAll('[data-enquiry]')].map(makeCard);
  const viewings = [...board.querySelectorAll('[data-viewing]')].map(makeCard);
  const winner = makeCard(board.querySelector('[data-winner]'));
  const finalViewing = viewings.find(viewing => viewing.slot.dataset.viewing === winner.slot.dataset.winner);
  const bookingFor = new Map(viewings.map(viewing => [viewing.slot.dataset.viewing, viewing]));
  const captions = [
    [0, 'Twelve enquiries arrive.'],
    [3000, 'Six applicants make the shortlist.'],
    [5000, 'Four applicants book a viewing.'],
    [8000, 'Two applicants cancel their viewings.'],
    [10000, 'Two applicants remain after cancellations.'],
    [11200, `${winner.card.querySelector('strong').textContent} is selected for rent.`],
  ];
  let elapsed = 0;
  let startedAt = 0;
  let frame = null;

  function makeCard(slot) {
    return { slot, card: slot.firstElementChild };
  }

  function positionBetween(source, destination, fraction) {
    return `translate(${(destination.x - source.x) * fraction}px, ${(destination.y - source.y) * fraction}px)`;
  }

  function phase(time, start, end) {
    return Math.max(0, Math.min(1, (time - start) / (end - start)));
  }

  function smooth(fraction) {
    return fraction * fraction * (3 - 2 * fraction);
  }

  function paint(item, opacity, transform = '', state = '', moving = false) {
    const { card } = item;
    if (item.opacity !== opacity) {
      card.style.opacity = opacity;
      item.opacity = opacity;
    }
    if (item.transform !== transform) {
      card.style.transform = transform;
      item.transform = transform;
    }
    if (item.state !== state || item.moving !== moving) {
      card.className = `rental-animation__card ${state}${moving ? ' is-moving' : ''}`.trim();
      item.state = state;
      item.moving = moving;
    }
  }

  function render(time) {
    const still = reducedMotion.matches;
    for (const [index, enquiry] of enquiries.entries()) {
      const arrival = phase(time, 100 + index * 165, 480 + index * 165);
      const shortlisted = index % 2 === 0;
      const viewing = bookingFor.get(enquiry.slot.dataset.enquiry);
      const dropStart = 3150 + Math.floor(index / 2) * 105;
      const fade = shortlisted ? phase(time, 5550, 6190) : phase(time, dropStart, dropStart + 660);
      let opacity = still ? Number(time > 0) : smooth(arrival);
      let transform = arrival < 1 && !still ? `translateY(${-12 * (1 - arrival)}px)` : '';
      let moving = false;

      if (viewing) {
        const transfer = phase(time, viewing.bookingStart, viewing.bookingEnd);
        if (transfer === 1) opacity = 0;
        if (!still && transfer > 0 && transfer < 1) {
          transform = positionBetween(enquiry, viewing, smooth(transfer));
          moving = true;
        }
      } else if (fade > 0) {
        opacity = still ? Number(fade < 1) : 1 - smooth(fade);
        if (!still && !shortlisted) {
          transform = `translateY(${130 * fade * fade}px) rotate(${9 * fade}deg)`;
          moving = true;
        }
      }
      paint(enquiry, opacity, transform, shortlisted && time >= 3000 ? 'is-shortlisted' : '', moving);
    }

    for (const viewing of viewings) {
      const cancelled = viewing.slot.hasAttribute('data-cancels') && time >= viewing.cancelAt;
      const cancellationFade = cancelled ? phase(time, viewing.cancelAt + 690, viewing.cancelAt + 1120) : 0;
      const transfer = viewing === finalViewing ? phase(time, 10350, 11200) : 0;
      const moving = !still && transfer > 0 && transfer < 1;
      const booked = time >= viewing.bookingEnd && transfer < 1;
      const fade = still ? Number(cancellationFade === 1) : smooth(cancellationFade);
      const opacity = booked ? 1 - fade : 0;
      const state = cancelled ? 'is-cancelled' : moving ? 'is-selected' : '';
      paint(viewing, opacity, moving ? positionBetween(viewing, winner, smooth(transfer)) : '', state, moving);
    }
    paint(winner, Number(time >= 11200));

    const message = time > 0 ? captions.findLast(([start]) => time >= start)[1] : 'Play the rental journey.';
    if (caption.textContent !== message) caption.textContent = message;
    progress.value = time;
  }

  function measure() {
    for (const item of [...enquiries, ...viewings, winner]) {
      const { x, y, width, height } = item.slot.getBoundingClientRect();
      item.x = x + width / 2;
      item.y = y + height / 2;
    }
    render(elapsed);
  }

  function tick(now) {
    elapsed = Math.max(0, Math.min(progress.max, now - startedAt));
    render(elapsed);
    if (elapsed < progress.max) {
      frame = requestAnimationFrame(tick);
    } else {
      frame = null;
      button.textContent = 'Replay';
    }
  }

  for (const [index, viewing] of viewings.entries()) {
    viewing.bookingStart = 5100 + index * 575;
    viewing.bookingEnd = viewing.bookingStart + 800;
    viewing.cancelAt = 8050 + index * 180;
  }

  section.querySelector('.rental-animation__fallback').hidden = true;
  player.hidden = false;
  button.hidden = false;
  measure();
  new ResizeObserver(measure).observe(board);
  reducedMotion.addEventListener('change', () => render(elapsed));

  button.addEventListener('click', () => {
    if (frame !== null) {
      cancelAnimationFrame(frame);
      frame = null;
      button.textContent = 'Resume';
      return;
    }
    if (elapsed === progress.max) {
      elapsed = 0;
      render(elapsed);
    }
    button.textContent = 'Pause';
    startedAt = performance.now() - elapsed;
    frame = requestAnimationFrame(tick);
  });
}

document.querySelectorAll('.rental-animation').forEach(mountRentalAnimation);
