// app/static/js/calendar.js
document.addEventListener('DOMContentLoaded', function() {
  var calendarEl = document.getElementById('calendar');
  var modalEl   = document.getElementById('modalEvent');
  var modal     = new bootstrap.Modal(modalEl);

  var calendar = new FullCalendar.Calendar(calendarEl, {
    initialView:   'dayGridMonth',
    headerToolbar: {
      left:   'prev,next today',
      center: 'title',
      right:  'dayGridMonth,timeGridWeek,timeGridDay,listWeek'
    },
    locale:       'pt',
    nowIndicator: true,
    selectable:   true,
    editable:     true,
    businessHours:{
      daysOfWeek:[1,2,3,4,5],
      startTime: '09:00',
      endTime:   '18:00'
    },
    slotMinTime: '07:00',
    slotMaxTime: '20:00',
    events: '/events',
    
    eventClick: function(info) {
      var ev    = info.event;
      var props = ev.extendedProps;
      
      // Título do modal
      modalEl.querySelector('.modal-title').innerText = ev.title;
      
      // Corpo do modal
      var body = '<p><strong>Data:</strong> ' + ev.start.toLocaleDateString() + '</p>';
      if (ev.end) {
        body += '<p><strong>Fim:</strong> ' + ev.end.toLocaleDateString() + '</p>';
      }
      body += '<p><strong>Tipo:</strong> ' + (props.type === 'task' ? 'Tarefa' : 'Prazo') + '</p>';
      modalEl.querySelector('.modal-body').innerHTML = body;
      
      // Footer com link apropriado
      var footer = modalEl.querySelector('.modal-footer');
      footer.innerHTML = '';
      if (props.type === 'task') {
        footer.innerHTML = '<a href="' + props.url_history + '" class="btn btn-primary">Ver Histórico</a>';
      } else {
        footer.innerHTML = '<a href="' + props.url_detail  + '" class="btn btn-primary">Ver Detalhes</a>';
      }
      
      modal.show();
    }
  });

  calendar.render();
});
