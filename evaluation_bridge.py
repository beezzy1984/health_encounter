# Stuff that translates evaluations to encounters
from datetime import timedelta
from trytond.modules.health.health import HealthInstitution

DELAY = timedelta(0, 120)  # artificial 2 minute delay


def reductor(ev):
    def real_reductor(a, b):
        if a and isinstance(a, (str, unicode)):
            return (getattr(ev, a) and a) or (getattr(ev, b) and b)
        else:
            return b

    return real_reductor

def Id(val):
    if val and hasattr(val, 'id'):
        return val.id
    else:
        return val

def make_encounter(ev):
    '''returns a tuple with an encounter dict and a list of
    component dicts .

    ({encounter_data}, [{component0}, {component1}])
    '''
    start_time = ev.evaluation_start
    end_time = ev.evaluation_endtime
    insti = ev.institution
    if not insti:
        insti = 140

    encounter = {
        'patient': Id(ev.patient),
        'start_time': start_time,
        'end_time': end_time,
        'state': ev.state,
        'appointment': Id(ev.evaluation_date),
        'next_appointment': Id(ev.next_evaluation),
        'signed_by': Id(ev.signed_by),
        'sign_time': ev.write_date,
        'institution': Id(insti),
        'primary_complaint': ev.chief_complaint,
        'fvty': ev.first_visit_this_year}
    components = []
    if ev.weight or ev.height or ev.abdominal_circ or ev.hip:
        comp = {
            'model': 'gnuhealth.encounter.anthropometry',
            'weight': ev.weight,
            'height': ev.height,
            'bmi': ev.bmi,
            'head_circumference': ev.head_circumference,
            'abdominal_circ': ev.abdominal_circ,
            'hip': ev.hip,
            'whr': ev.whr}
        components.append(comp)
    reducer = reductor(ev)
    ambu_fields = ['dehydration', 'temperature', 'osat', 'bpm',
                   'respiratory_rate', 'cholesterol_total', 'glycemia',
                   'ldl', 'hdl', 'tag', 'hba1c', 'systolic', 'diastolic',
                   'notes_complaint']

    if reduce(reducer, ambu_fields):
        ambu_fields = ambu_fields[1:-1]
        comp = {'model': 'gnuhealth.encounter.ambulatory',
                'notes': ev.notes_complaint}
        comp.update([(field, getattr(ev, field)) for field in ambu_fields])
        if ev.dehydration:
            comp.update(dehydration='moderate')
        components.append(comp)

    mental_fields = ['judgment', 'tremor', 'violent', 'mood', 'orientation',
                     'knowledge_current_events', 'abstraction', 'memory',
                     'vocabulary', 'calculation_ability', 'object_recognition',
                     'praxis']

    if reduce(reducer, mental_fields):
        mental_fields.extend(['loc', 'loc_eyes', 'loc_verbal', 'loc_motor'])
        del mental_fields[0]
        comp = {'model': 'gnuhealth.encounter.mental_status',
                'judgement': ev.judgment}
        comp.update([(fld, getattr(ev, fld)) for fld in mental_fields])
        components.append(comp)

    clinical_fields = ['diagnosis', 'info_diagnosis', 'directions',
                       'diagnostic_hypothesis', 'secondary_conditions',
                       'signs_and_symptoms']
    if reduce(reducer, clinical_fields):
        comp = {'model': 'gnuhealth.encounter.clinical',
                'diagnosis': Id(ev.diagnosis)}
        for comp_field, ev_field in [('diagnostic_hypothesis', 'diagnostic_hypothesis'),
                                     ('secondary_conditions', 'secondary_conditions'),
                                     ('signs_symptoms', 'signs_and_symptoms')]:
            ev_fld_data = getattr(ev, ev_field)
            if ev_fld_data:
                comp[comp_field] = [('add',
                                    [x.id for x in ev_fld_data])]
        comp_notes = filter(None, [ev.info_diagnosis, ev.notes])
        comp['notes'] = '\n'.join(comp_notes)
        comp['treatment_plan'] = ev.directions
        components.append(comp)

    if ev.actions:
        comp = {'model': 'gnuhealth.encounter.procedures',
                'procedures': [('add',
                                [x.id for x in ev.actions])]}
        components.append(comp)

    for comp in components:
        comp.update(
            performed_by=Id(ev.healthprof),
            signed_by=Id(ev.signed_by),
            start_time=start_time,
            end_time=end_time
        )
    return (encounter, components)


def create_encounter(ev, pool):
    encd, comps = make_encounter(ev)
    # first setup the encounter object
    Encounter = pool.get('gnuhealth.encounter')

    enc_list = Encounter.create([encd], {})
    enc = enc_list[0]
    for x in comps:
        model_name = x.pop('model')
        model = pool.get(model_name)
        x.update(encounter=enc)
        model.create([x], {})
    ev.encounter = Encounter(enc)
    ev.save()
    return enc
