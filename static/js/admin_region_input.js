// Django admin: suggest the chosen church's regions in the typed region box,
// and switch the suggestions whenever a different church is chosen.
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('input[data-region-names]').forEach((input) => {
        const data = document.getElementById(input.dataset.regionNames);
        const list = document.getElementById(input.getAttribute('list'));
        const church = document.getElementById(input.dataset.churchField);
        if (!data || !list) return;

        const namesByChurch = JSON.parse(data.textContent);
        const refresh = () => {
            const names = namesByChurch[church ? church.value : ''] || [];
            list.replaceChildren(...names.map((name) => {
                const option = document.createElement('option');
                option.value = name;
                return option;
            }));
        };

        if (church) {
            church.addEventListener('change', refresh);
            // The admin theme turns the church dropdown into a searchable
            // Select2 box, which announces a new choice through jQuery rather
            // than a normal browser event, so listen through jQuery as well.
            [window.jQuery, window.django && window.django.jQuery]
                .filter((jq, index, all) => jq && all.indexOf(jq) === index)
                .forEach((jq) => jq(church).on('change', refresh));
        }
        refresh();
    });
});
