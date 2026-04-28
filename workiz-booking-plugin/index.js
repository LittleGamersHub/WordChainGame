import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";
import fetch from "node-fetch";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
const WORKIZ_API_BASE = "https://api.workiz.com/api/v1";
const SECRET_KEY = process.env.WORKIZ_SECRET_KEY;
const ACCOUNT_ID = process.env.WORKIZ_ACCOUNT_ID; // optional – used for user-facing messages

if (!SECRET_KEY) {
  console.error(
    "[workiz-booking-plugin] WORKIZ_SECRET_KEY environment variable is required."
  );
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Workiz API helpers
// ---------------------------------------------------------------------------
/**
 * Make an authenticated request to the Workiz REST API.
 * Workiz uses the secret key embedded directly in the URL path.
 */
async function workizRequest(path, { method = "GET", body } = {}) {
  const url = `${WORKIZ_API_BASE}/${SECRET_KEY}${path}`;
  const headers = { "Content-Type": "application/json", Accept: "application/json" };
  const options = { method, headers };
  if (body) options.body = JSON.stringify(body);

  const response = await fetch(url, options);
  const text = await response.text();

  let data;
  try {
    data = JSON.parse(text);
  } catch {
    data = { raw: text };
  }

  if (!response.ok) {
    throw new Error(
      `Workiz API error ${response.status}: ${JSON.stringify(data)}`
    );
  }
  return data;
}

// ---------------------------------------------------------------------------
// Tool schemas (Zod for input validation, converted to JSON Schema for MCP)
// ---------------------------------------------------------------------------
const GetServicesSchema = z.object({});

const GetAvailableSlotsSchema = z.object({
  service_name: z.string().describe("The name of the service to check availability for"),
  start_date: z
    .string()
    .describe("Start date to search for available slots (YYYY-MM-DD)"),
  end_date: z
    .string()
    .describe("End date to search for available slots (YYYY-MM-DD)"),
  zip_code: z
    .string()
    .optional()
    .describe("Customer ZIP code to check service area coverage"),
});

const BookServiceSchema = z.object({
  first_name: z.string().describe("Customer first name"),
  last_name: z.string().describe("Customer last name"),
  phone: z.string().describe("Customer phone number (digits only, e.g. 5551234567)"),
  email: z.string().email().describe("Customer email address"),
  address: z.string().describe("Service address (street)"),
  city: z.string().describe("Service city"),
  state: z.string().describe("Service state (2-letter code, e.g. CA)"),
  zip: z.string().describe("Service ZIP code"),
  service_name: z.string().describe("Name of the service to book"),
  job_date: z.string().describe("Appointment date (YYYY-MM-DD)"),
  job_time: z.string().describe("Appointment start time (HH:MM, 24-hour)"),
  job_end_time: z
    .string()
    .optional()
    .describe("Appointment end time (HH:MM, 24-hour)"),
  notes: z
    .string()
    .optional()
    .describe("Additional notes or special instructions for the technician"),
});

const GetJobStatusSchema = z.object({
  job_id: z.string().describe("The Workiz job UUID or ID returned when the job was booked"),
});

// ---------------------------------------------------------------------------
// Helper: convert a Zod object schema to a JSON Schema compatible object
// ---------------------------------------------------------------------------
function zodToJsonSchema(schema) {
  const shape = schema.shape;
  const properties = {};
  const required = [];

  for (const [key, field] of Object.entries(shape)) {
    const isOptional =
      field instanceof z.ZodOptional || field._def?.typeName === "ZodOptional";
    const innerField = isOptional ? field.unwrap() : field;

    let type = "string";
    if (innerField instanceof z.ZodNumber) type = "number";
    else if (innerField instanceof z.ZodBoolean) type = "boolean";
    else if (innerField instanceof z.ZodArray) type = "array";
    else if (innerField instanceof z.ZodObject) type = "object";

    const prop = { type };
    if (innerField._def?.description) prop.description = innerField._def.description;
    properties[key] = prop;
    if (!isOptional) required.push(key);
  }

  return { type: "object", properties, required };
}

// ---------------------------------------------------------------------------
// Tool definitions exposed to Claude
// ---------------------------------------------------------------------------
const TOOLS = [
  {
    name: "workiz_get_services",
    description:
      "List all service types configured in the Workiz account. Call this first so the customer can choose which service they need.",
    inputSchema: zodToJsonSchema(GetServicesSchema),
  },
  {
    name: "workiz_get_available_slots",
    description:
      "Retrieve available appointment time slots for a specific Workiz service within a date range. Use this after the customer selects a service so they can pick a convenient time.",
    inputSchema: zodToJsonSchema(GetAvailableSlotsSchema),
  },
  {
    name: "workiz_book_service",
    description:
      "Create a new job/booking in Workiz on behalf of the customer. Gather all required customer details (name, phone, email, address, preferred date/time, service) before calling this tool.",
    inputSchema: zodToJsonSchema(BookServiceSchema),
  },
  {
    name: "workiz_get_job_status",
    description:
      "Look up the current status and details of an existing Workiz job by its ID. Use this to confirm a booking or answer customer questions about their appointment.",
    inputSchema: zodToJsonSchema(GetJobStatusSchema),
  },
];

// ---------------------------------------------------------------------------
// Tool handlers
// ---------------------------------------------------------------------------
async function handleGetServices() {
  const data = await workizRequest("/services/");

  // Workiz returns services in data.data or similar – normalise gracefully
  const services =
    data?.data ?? data?.services ?? data?.result ?? data ?? [];

  const list = Array.isArray(services) ? services : Object.values(services);

  if (list.length === 0) {
    return "No services are currently configured in this Workiz account.";
  }

  const formatted = list.map((svc, i) => {
    const name = svc.name ?? svc.service_name ?? svc.title ?? `Service ${i + 1}`;
    const desc = svc.description ?? svc.desc ?? "";
    const duration = svc.duration ? ` | Duration: ${svc.duration} min` : "";
    const price = svc.price ? ` | Price: $${svc.price}` : "";
    return `${i + 1}. ${name}${duration}${price}${desc ? ` — ${desc}` : ""}`;
  });

  return `Available services:\n${formatted.join("\n")}`;
}

async function handleGetAvailableSlots({ service_name, start_date, end_date, zip_code }) {
  const params = new URLSearchParams({ startDate: start_date, endDate: end_date });
  if (service_name) params.set("serviceType", service_name);
  if (zip_code) params.set("zip", zip_code);

  const data = await workizRequest(`/availability/?${params.toString()}`);
  const slots =
    data?.data ?? data?.slots ?? data?.availability ?? data?.result ?? data ?? [];

  const list = Array.isArray(slots) ? slots : Object.values(slots);

  if (list.length === 0) {
    return `No available slots found for "${service_name}" between ${start_date} and ${end_date}. Try a wider date range or different service.`;
  }

  const formatted = list.map((slot, i) => {
    const date = slot.date ?? slot.job_date ?? slot.start_date ?? "Unknown date";
    const time = slot.time ?? slot.start_time ?? slot.job_time ?? "Unknown time";
    const endTime = slot.end_time ?? slot.job_end_time ?? "";
    const label = slot.label ?? slot.display ?? "";
    return `${i + 1}. ${date} at ${time}${endTime ? ` – ${endTime}` : ""}${label ? ` (${label})` : ""}`;
  });

  return `Available appointment slots for "${service_name}" from ${start_date} to ${end_date}:\n${formatted.join("\n")}`;
}

async function handleBookService(args) {
  const payload = {
    firstName: args.first_name,
    lastName: args.last_name,
    phone: args.phone,
    email: args.email,
    address: args.address,
    city: args.city,
    state: args.state,
    zip: args.zip,
    jobType: args.service_name,
    jobDate: args.job_date,
    jobTime: args.job_time,
    ...(args.job_end_time && { jobEndTime: args.job_end_time }),
    ...(args.notes && { jobDescription: args.notes }),
    source: "Claude AI Booking",
  };

  const data = await workizRequest("/job/create/", { method: "POST", body: payload });

  const jobId = data?.data?.uuid ?? data?.uuid ?? data?.job_id ?? data?.id ?? null;
  const confirmationMsg = jobId
    ? `Job ID: ${jobId}`
    : "Job created (no ID returned — check Workiz dashboard)";

  return (
    `Booking confirmed!\n` +
    `${confirmationMsg}\n` +
    `Customer: ${args.first_name} ${args.last_name}\n` +
    `Service: ${args.service_name}\n` +
    `Date: ${args.job_date} at ${args.job_time}\n` +
    `Address: ${args.address}, ${args.city}, ${args.state} ${args.zip}\n\n` +
    `A confirmation will be sent to ${args.email}.`
  );
}

async function handleGetJobStatus({ job_id }) {
  const data = await workizRequest(`/job/${encodeURIComponent(job_id)}/`);
  const job = data?.data ?? data?.job ?? data ?? {};

  const status = job.status ?? job.jobStatus ?? "Unknown";
  const tech = job.techName ?? job.technician ?? job.assignedTo ?? "Unassigned";
  const date = job.jobDate ?? job.date ?? "Unknown";
  const time = job.jobTime ?? job.time ?? "Unknown";
  const address = job.address
    ? `${job.address}, ${job.city ?? ""}, ${job.state ?? ""} ${job.zip ?? ""}`
    : "Unknown";
  const customer =
    job.firstName && job.lastName
      ? `${job.firstName} ${job.lastName}`
      : job.clientName ?? "Unknown";

  return (
    `Job ${job_id} Status:\n` +
    `Status: ${status}\n` +
    `Customer: ${customer}\n` +
    `Date: ${date} at ${time}\n` +
    `Address: ${address}\n` +
    `Technician: ${tech}`
  );
}

// ---------------------------------------------------------------------------
// MCP Server setup
// ---------------------------------------------------------------------------
const server = new Server(
  { name: "workiz-booking-plugin", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    let text;
    switch (name) {
      case "workiz_get_services":
        text = await handleGetServices();
        break;
      case "workiz_get_available_slots":
        GetAvailableSlotsSchema.parse(args);
        text = await handleGetAvailableSlots(args);
        break;
      case "workiz_book_service":
        BookServiceSchema.parse(args);
        text = await handleBookService(args);
        break;
      case "workiz_get_job_status":
        GetJobStatusSchema.parse(args);
        text = await handleGetJobStatus(args);
        break;
      default:
        throw new Error(`Unknown tool: ${name}`);
    }
    return { content: [{ type: "text", text }] };
  } catch (err) {
    return {
      content: [{ type: "text", text: `Error: ${err.message}` }],
      isError: true,
    };
  }
});

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------
const transport = new StdioServerTransport();
await server.connect(transport);
console.error(
  `[workiz-booking-plugin] MCP server started${ACCOUNT_ID ? ` for account ${ACCOUNT_ID}` : ""}.`
);
