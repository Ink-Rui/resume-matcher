/* ============================================================
   app.js —— 前端交互逻辑

   三件事：
   1. 切换「上传文件 / 粘贴文本」两个标签页
   2. 收集表单数据，用 fetch 提交到后端 /api/analyze
   3. 把返回的 JSON 渲染成界面上的分数、关键词和联系
   ============================================================ */

(function () {
  "use strict";

  // ---------- 选择界面元素 ----------
  var tabs        = document.querySelectorAll(".tab");
  var panes       = document.querySelectorAll(".tab-pane");
  var fileInput   = document.getElementById("resumeFile");
  var resumeText  = document.getElementById("resumeText");
  var jdText      = document.getElementById("jdText");
  var degreeSel   = document.getElementById("degree");
  var yearsInput  = document.getElementById("workYears");
  var analyzeBtn  = document.getElementById("analyzeBtn");

  var states = {
    empty:   document.getElementById("emptyState"),
    loading: document.getElementById("loadingState"),
    error:   document.getElementById("errorState"),
    result:  document.getElementById("resultState")
  };
  var currentTab = "file";

  // ---------- 1. 标签页切换 ----------
  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      currentTab = tab.dataset.tab;
      tabs.forEach(function (t) { t.classList.toggle("active", t === tab); });
      panes.forEach(function (p) {
        p.classList.toggle("active", p.dataset.pane === currentTab);
      });
    });
  });

  // ---------- 2. 状态切换 ----------
  function showState(name) {
    Object.keys(states).forEach(function (k) {
      states[k].classList.toggle("hidden", k !== name);
    });
  }

  // ---------- 3. 提交分析 ----------
  analyzeBtn.addEventListener("click", function () {
    var jd = jdText.value.trim();
    if (!jd) {
      showError("请先在「第 2 步」粘贴岗位 JD 内容。");
      return;
    }
    if (currentTab === "file" && !fileInput.files.length) {
      showError("请选择简历文件，或切换到「粘贴文本」把简历内容贴进来。");
      return;
    }
    if (currentTab === "text" && !resumeText.value.trim()) {
      showError("请把简历内容粘贴到文本框。");
      return;
    }

    var form = new FormData();
    if (currentTab === "file") {
      form.append("resume_file", fileInput.files[0]);
    } else {
      form.append("resume_text", resumeText.value.trim());
    }
    form.append("jd_text", jd);
    form.append("degree", degreeSel.value);
    form.append("work_years", yearsInput.value || "0");

    analyzeBtn.disabled = true;
    analyzeBtn.textContent = "分析中…";
    showState("loading");

    // 简单的步骤提示动画，让等待过程不像卡死
    var steps = ["解析简历文件", "提取岗位关键词", "计算加权匹配度", "生成改进建议"];
    var stepIdx = 0;
    var stepTimer = setInterval(function () {
      stepIdx = (stepIdx + 1) % steps.length;
      document.getElementById("loadingStep").textContent = steps[stepIdx];
    }, 900);

    fetch("/api/analyze", { method: "POST", body: form })
      .then(function (r) { return r.json(); })
      .then(function (res) {
        if (!res.ok) { showError(res.error || "分析失败"); return; }
        render(res.data);
      })
      .catch(function (err) {
        showError("请求失败：" + err.message + "（请确认后端服务仍在运行）");
      })
      .finally(function () {
        clearInterval(stepTimer);
        analyzeBtn.disabled = false;
        analyzeBtn.textContent = "开始分析";
      });
  });

  function showError(msg) {
    document.getElementById("errorMsg").textContent = msg;
    showState("error");
  }

  // ---------- 4. 渲染结果 ----------
  function render(d) {
    // --- 分数环 ---
    var score = d.score;
    var ring = document.getElementById("scoreRing");
    var deg = Math.round(score / 100 * 360);
    ring.style.background =
      "conic-gradient(var(--primary) " + deg + "deg, #E8EDF4 " + deg + "deg)";
    animateNumber(document.getElementById("scoreNum"), score);
    document.getElementById("scoreGrade").textContent = d.grade;

    var detail = "加权技能匹配 " + d.raw_score + " 分，命中 " +
                 d.skill_hit + "/" + d.skill_total + " 项要求";
    if (d.penalty > 0) {
      detail += "，因门槛不符扣除 " + d.penalty + " 分";
    }
    document.getElementById("scoreDetail").textContent = detail;

    // --- 三张门槛卡 ---
    setGate("gateSkill", "技能匹配", d.skill_hit + " / " + d.skill_total,
            d.skill_total > 0 && d.skill_hit > 0);

    var degReq = d.degree.required;
    setGate("gateDegree",
            "学历门槛",
            degReq ? (d.degree.ok ? "符合 " + degReq : "要求 " + degReq + "（你不符）") : "未提及",
            degReq ? d.degree.ok : true);

    var expReq = d.experience.required;
    setGate("gateExp",
            "经验门槛",
            expReq ? (d.experience.ok ? "符合 " + expReq + " 年" : "要求 " + expReq + " 年（你不符）")
                   : "未提及",
            expReq ? d.experience.ok : true);

    // --- 关键词 ---
    document.getElementById("hitCount").textContent = d.skill_hit;
    document.getElementById("missCount").textContent = d.missing.length;
    renderChips("hitChips", d.hit, false);
    renderChips("missChips", d.missing, true);

    // --- 门槛提示 ---
    var notesList = document.getElementById("notesList");
    notesList.innerHTML = "";
    if (!d.notes || !d.notes.length) {
      document.getElementById("notesBlock").classList.add("hidden");
    } else {
      document.getElementById("notesBlock").classList.remove("hidden");
      d.notes.forEach(function (n) {
        var li = document.createElement("li");
        li.textContent = n;
        notesList.appendChild(li);
      });
    }

    // --- 改进建议（AI 优先，没有就用规则建议）---
    var adviceBox = document.getElementById("adviceBox");
    var adviceTitle = document.getElementById("adviceTitle");
    var oldNote = document.querySelector(".advice-note");
    if (oldNote) { oldNote.remove(); }

    if (d.ai_advice) {
      adviceTitle.textContent = "AI 改进建议";
      adviceBox.classList.remove("is-rule");
      adviceBox.textContent = d.ai_advice;
    } else {
      adviceTitle.textContent = "改进建议（规则生成）";
      adviceBox.classList.add("is-rule");
      adviceBox.textContent = (d.suggestions || []).join("\n");
      if (d.ai_advice_error) {
        var note = document.createElement("p");
        note.className = "advice-note";
        note.textContent = "提示：" + d.ai_advice_error;
        adviceBox.parentNode.insertBefore(note, adviceBox.nextSibling);
      }
    }

    // --- 原始文本 ---
    document.getElementById("resumeSource").textContent = d.resume_source || "—";
    document.getElementById("resumePreview").textContent = d.resume_preview || "—";
    document.getElementById("jdPreview").textContent = d.jd_preview || "—";

    showState("result");
  }

  function setGate(id, label, value, pass) {
    var el = document.getElementById(id);
    el.classList.toggle("pass", !!pass);
    el.classList.toggle("fail", !pass);
    el.querySelector(".gate-label").textContent = label;
    el.querySelector(".gate-value").textContent = value;
  }

  function renderChips(containerId, items, isMiss) {
    var box = document.getElementById(containerId);
    box.innerHTML = "";
    if (!items || !items.length) {
      var empty = document.createElement("span");
      empty.className = "chip miss";
      empty.textContent = isMiss ? "没有缺失项，匹配得很好" : "暂无命中项";
      box.appendChild(empty);
      return;
    }
    items.forEach(function (it) {
      var span = document.createElement("span");
      span.className = "chip " + (isMiss ? "miss" : "hit");
      if (isMiss && it.weight >= 1.5) { span.className = "chip miss high"; }
      span.textContent = it.name;
      var w = document.createElement("span");
      w.className = "w";
      w.textContent = "×" + it.weight;
      span.appendChild(w);
      box.appendChild(span);
    });
  }

  // 数字从 0 滚动到目标值，纯视觉细节
  function animateNumber(el, target) {
    var start = 0;
    var duration = 600;
    var t0 = performance.now();
    function frame(now) {
      var p = Math.min((now - t0) / duration, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(start + (target - start) * eased);
      if (p < 1) { requestAnimationFrame(frame); }
    }
    requestAnimationFrame(frame);
  }

})();
