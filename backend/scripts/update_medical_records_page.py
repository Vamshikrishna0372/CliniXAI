with open("clinixai-health-flow/src/routes/app.medical-records.tsx", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Update Route definition with validateSearch
route_old = """export const Route = createFileRoute("/app/medical-records")({
  head: () => ({ meta: [{ title: "Medical Records — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  component: MedicalRecordsPage,
});"""

route_new = """export const Route = createFileRoute("/app/medical-records")({
  head: () => ({ meta: [{ title: "Medical Records — CliniXAI" }, { name: "robots", content: "noindex" }] }),
  validateSearch: (search: Record<string, unknown>) => ({
    patient_id: typeof search.patient_id === "string" ? search.patient_id : typeof search.patientId === "string" ? search.patientId : undefined,
  }),
  component: MedicalRecordsPage,
});"""

text = text.replace(route_old, route_new)

# 2. Update MedicalRecordsPage selected patient logic
body_old = """function MedicalRecordsPage() {
  const { user } = useAuth();
  const { patients, appointments } = useClinix();

  const isDoctor = user?.role === "doctor";
  const isStaff = user?.role === "staff";
  const isAdmin = user?.role === "admin";
  const canManageRecords = isDoctor || isStaff || isAdmin;

  // Authorized patients for doctors (derived from appointments or full patient list for staff/admin)
  const availablePatients = useMemo(() => {
    if (!canManageRecords) return [];
    if (isDoctor) {
      const aptPats = new Set(appointments.map((a) => a.patientId));
      return patients.filter((p) => aptPats.has(p.id));
    }
    return patients;
  }, [patients, appointments, canManageRecords, isDoctor]);

  // Selected patient for doctor / staff / admin view
  const myPatient = patients.find((p) => p.email === user?.email || p.id === user?.id);
  const initialPatientId = canManageRecords
    ? (availablePatients[0]?.id || "")
    : (myPatient ? myPatient.id : "");

  const [selectedPatientId, setSelectedPatientId] = useState<string>(initialPatientId);"""

body_new = """function MedicalRecordsPage() {
  const { user } = useAuth();
  const { patients, appointments } = useClinix();
  const search = Route.useSearch();
  const searchPatId = search.patient_id;

  const isDoctor = user?.role === "doctor";
  const isStaff = user?.role === "staff";
  const isAdmin = user?.role === "admin";
  const canManageRecords = isDoctor || isStaff || isAdmin;

  // Authorized patients for doctors (derived from appointments or full patient list for staff/admin)
  const availablePatients = useMemo(() => {
    if (!canManageRecords) return [];
    if (isDoctor) {
      const aptPats = new Set(appointments.map((a) => a.patientId));
      if (searchPatId) aptPats.add(searchPatId);
      return patients.filter((p) => aptPats.has(p.id) || p.id === searchPatId);
    }
    return patients;
  }, [patients, appointments, canManageRecords, isDoctor, searchPatId]);

  // Selected patient for doctor / staff / admin view
  const myPatient = patients.find((p) => p.email === user?.email || p.id === user?.patientId || p.id === user?.id);
  const myPatId = (user?.patientId && user.patientId.startsWith("PAT-"))
    ? user.patientId
    : (myPatient?.id && myPatient.id.startsWith("PAT-"))
      ? myPatient.id
      : (user?.id || "");

  const initialPatientId = searchPatId
    ? searchPatId
    : canManageRecords
      ? (availablePatients[0]?.id || "")
      : myPatId;

  const [selectedPatientId, setSelectedPatientId] = useState<string>(initialPatientId);

  useEffect(() => {
    if (searchPatId && searchPatId !== selectedPatientId) {
      setSelectedPatientId(searchPatId);
    }
  }, [searchPatId]);"""

text = text.replace(body_old, body_new)

with open("clinixai-health-flow/src/routes/app.medical-records.tsx", "w", encoding="utf-8", newline="") as f:
    f.write(text)

print("Updated app.medical-records.tsx successfully")

