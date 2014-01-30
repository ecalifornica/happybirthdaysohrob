// No idea what I'm doing.
$(document).ready(function worker(){
    $.ajax({
        if (data.voteone) {
            $('#voteone').addClass('btn-success');
        } else if (!data.voteone) {
            $('#voteone').removeClass('btn-success');
        };
    }, 
    complete: function() {
        setTimeout(worker, 3000);
    }
    });
    );
