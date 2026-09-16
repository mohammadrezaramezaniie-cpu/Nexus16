from pydantic import BaseModel
from crewai import Task, Crew, Process
from crewai.flow.flow import Flow, start, listen
from agents import build_agents


class AgentOSState(BaseModel):
    request: str = ""
    execution_brief: str = ""
    plan: str = ""
    studio_direction: str = ""
    draft: str = ""
    qc: str = ""
    status: str = "NEW"


class AgentOSFlow(Flow[AgentOSState]):
    @start()
    def optimize_intent(self):
        agents = build_agents()
        task = Task(
            description=(
                "Transform the user's request into an execution brief. Preserve intent exactly. "
                "Infer hidden requirements that are necessary to satisfy the request. Include: desired outcome, "
                "constraints, definition of done, acceptance criteria, required evidence/tools and QA method. "
                "For website/app/product design, require visual-reference research before design. Select reference sources by task type: "
                "Landingfolio/Godly/Awwwards for marketing and landing pages; Mobbin/Refero/SaaSFrame for SaaS/product UI; "
                "and domain-leading real products such as Corva/Palantir/Datadog/Grafana for industrial and operational software. "
                "If the user names a visual/product reference such as Corva, treat reference fidelity as a hard requirement: "
                "analyze layout grammar, navigation, information density, typography, spacing, component treatment, chart grammar, "
                "interaction patterns, motion, data visualization sophistication and responsive behavior. Do NOT reduce the reference to colors/theme. "
                "Require rendered screenshot comparison and targeted revisions until visual, DataViz and reference-fidelity criteria pass. "
                f"USER REQUEST: {self.state.request}"
            ),
            expected_output="A precise execution brief with measurable acceptance criteria.",
            agent=agents["PO"],
        )
        result = Crew(agents=[agents["PO"]], tasks=[task], process=Process.sequential).kickoff()
        self.state.execution_brief = str(result)
        return self.state.execution_brief

    @listen(optimize_intent)
    def orchestrate(self):
        agents = build_agents()
        task = Task(
            description=(
                "Create the minimal high-quality specialist execution plan for this brief. "
                "Select only needed capability agents from CTX, STUDIO, BUILD, OPP, STR, FIN, LEGAL, RES, DATA, PRES, AUTO. "
                "For any website/app/UI/UX/product-visual task, STUDIO must run before BUILD. "
                "Always end important work with QC. For app/product work, require independent visual and technical review. "
                f"EXECUTION BRIEF:\n{self.state.execution_brief}"
            ),
            expected_output="Ordered agent plan, dependencies, tools and revision gates.",
            agent=agents["EX"],
        )
        result = Crew(agents=[agents["EX"]], tasks=[task], process=Process.sequential).kickoff()
        self.state.plan = str(result)
        return self.state.plan

    @listen(orchestrate)
    def execute_and_qc(self):
        agents = build_agents()
        request_lower = self.state.request.lower()
        is_product_design = any(x in request_lower for x in [
            "app", "software", "site", "website", "ui", "ux", "dashboard",
            "اپ", "نرم افزار", "نرم‌افزار", "سایت", "داشبورد", "ظاهر", "طراحی"
        ])

        tasks = []
        crew_agents = []
        studio_task = None

        if is_product_design:
            studio_task = Task(
                description=(
                    "Act as Studio before implementation. Produce the visual/product direction required by the execution brief. "
                    "First classify the product, then research/decompose 5-10 relevant references from the appropriate source class. "
                    "Do not copy a single design. Extract reusable patterns for layout, navigation, density, spacing, typography, visual hierarchy, "
                    "primary visualization composition, card/panel treatment, chart grammar, interaction, motion and responsive behavior. "
                    "If a named reference exists, explicitly state which structural/interaction qualities must be preserved. "
                    "For existing products, identify what should be preserved and what should be evolved. "
                    "For analytical/industrial products, define domain-aware DataViz requirements and prohibit decorative/static mock charts for operational data. "
                    "End with a concrete Visual Specification and screenshot-based acceptance checklist for BUILD. "
                    f"EXECUTION BRIEF:\n{self.state.execution_brief}\nPLAN:\n{self.state.plan}"
                ),
                expected_output=(
                    "Reference research summary, visual decomposition, preserve/evolve decisions, design direction, DataViz specification, "
                    "and measurable screenshot/reference-fidelity acceptance checklist."
                ),
                agent=agents["STUDIO"],
            )
            tasks.append(studio_task)
            crew_agents.append(agents["STUDIO"])

        execution = Task(
            description=(
                "Execute the request according to the execution brief and plan. "
                "For software/reference-driven UI tasks: follow Studio's visual specification, preserve strong existing architecture, "
                "use real domain-aware data visualization rather than decorative mock charts, and make rendered visual output part of completion. "
                "Do not claim completion until implementation evidence exists. "
                f"BRIEF:\n{self.state.execution_brief}\nPLAN:\n{self.state.plan}"
            ),
            expected_output="Best possible specialist output plus evidence of completion.",
            agent=agents["BUILD"] if is_product_design else agents["RES"],
            context=[studio_task] if studio_task else None,
        )
        tasks.append(execution)
        crew_agents.append(execution.agent)

        qc = Task(
            description=(
                "Independently audit the specialist output against every acceptance criterion in the execution brief. "
                "Do not approve based only on build/tests. For reference-driven software, independently score Product Fit, UX, Technical Quality, "
                "Visual Quality, DataViz Quality and Reference Fidelity. Verify screenshot/render evidence when required. "
                "If any hard criterion fails, return FAIL with targeted revisions. Reference-driven design should normally require >=8.5/10 "
                "for Visual Quality, DataViz Quality and Reference Fidelity before PASS."
            ),
            expected_output="PASS or FAIL, dimension scores, defects and targeted revision instructions.",
            agent=agents["QC"],
            context=[execution] + ([studio_task] if studio_task else []),
        )
        tasks.append(qc)
        crew_agents.append(agents["QC"])

        result = Crew(agents=crew_agents, tasks=tasks, process=Process.sequential).kickoff()
        self.state.draft = str(result)
        self.state.qc = str(result)
        self.state.status = "COMPLETED_WITH_QC"
        return result


if __name__ == "__main__":
    import sys
    flow = AgentOSFlow()
    flow.state.request = " ".join(sys.argv[1:]) or "Build a premium industrial application inspired by Corva."
    print(flow.kickoff())
