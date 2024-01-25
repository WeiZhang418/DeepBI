import React, { useState, useEffect, useCallback } from 'react';
import Button from "antd/lib/button";
import Form from "antd/lib/form";
import Input from "antd/lib/input";
import Radio from "antd/lib/radio";
import routeWithUserSession from "@/components/ApplicationArea/routeWithUserSession";
import wrapSettingsTab from "@/components/SettingsWrapper";
import routes from "@/services/routes";
import { axios } from "@/services/axios";
import Link from "@/components/Link";
import QuestionCircleOutlinedIcon from "@ant-design/icons/QuestionCircleOutlined";
import { createWebSocket, closeWebSocket } from '../testdialogue/components/Dialogue/websocket';
import toast from 'react-hot-toast';
import { JSON_ROOT } from '@/services/api-key-data';
const SettingsOpenKey = () => {
  const [form] = Form.useForm();
  const [disabled, setDisabled] = useState(false);
  const [aiOption, setAiOption] = useState('DeepInsight');
  const [aiOptions, setAiOptions] = useState(JSON_ROOT);
  const [requiredFields, setRequiredFields] = useState({});

  const getOpenKey = useCallback(async () => {
    setDisabled(true);
    try {
      const { data } = await axios.get(`/api/ai_token`);
      // 合并接口数据和本地数据
      const mergedData = { ...aiOptions };
      Object.keys(data).forEach(key => {
        if(data[key]){
          mergedData[key] = { ...mergedData[key], ...data[key] };
        }
       
      });
      setAiOptions(mergedData);
      setRequiredFields(mergedData[data.in_use].required || []);
      setAiOption(data.in_use);
      form.setFieldsValue(mergedData[data.in_use]);
    } catch (error) {
      toast.error(window.W_L.fail);
    }
    createWebSocket();
    setDisabled(false);
  }, [form, aiOptions]);

  useEffect(() => {
    getOpenKey();
  }, [getOpenKey]);

  const handleOpenKey = useCallback(async (values) => {
    setDisabled(true);
    try {
      const response = await axios.post("/api/ai_token", {
        in_use: aiOption,
        ...aiOptions,
        [aiOption]: values
      });
      if (response.code === 200) {
        toast.success(window.W_L.save_success);
        getOpenKey();
      } else {
        toast.error(window.W_L.save_failed);
      }
    } catch (error) {
      toast.error(window.W_L.save_failed);
    }
    closeWebSocket();
    setDisabled(false);
  }, [aiOption, aiOptions, getOpenKey]);

  const onFinish = (values) => {
    handleOpenKey(values);
  };

  const handleRadioChange = e => {
    setAiOption(e.target.value);
    setRequiredFields(aiOptions[e.target.value].required || []);
  };

  const renderFormItems = () => {
    const currentOption = aiOptions[aiOption] || {};
    const requiredKeys = currentOption.required || [];
    return Object.keys(currentOption).filter(key => key !== 'required').map((key) => {
      return (
        <Form.Item
          key={key}
          name={key}
          label={key}
          rules={[{ required: requiredKeys.includes(key), message: `${window.W_L.please_enter}${key}` }]}
        >
          <Input placeholder={key} />
        </Form.Item>
      );
    });
  };

  return (
    <React.Fragment>
      <div className="row1" style={{ width: "50%", margin: "auto" }}>
        <Form
          form={form}
          layout="vertical"
          disabled={disabled}
          onFinish={onFinish}
        >
          <Form.Item>
            <div style={{ display: "flex", alignItems: "center" }}>
              <h4 style={{ marginRight: "30px" }}>AI:</h4>
              <Radio.Group onChange={handleRadioChange} value={aiOption}>
                {Object.keys(aiOptions).map(option => (
                  <Radio key={option} value={option}>{option}</Radio>
                ))}
              </Radio.Group>
            </div>
          </Form.Item>
          {renderFormItems()}
          <Form.Item style={{ textAlign: "right" }}>
            <div style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center" }}>
                <QuestionCircleOutlinedIcon style={{ marginRight: "3px", color: "#2196f3" }} />
                <Link
                  href="https://holmes.bukeshiguang.com/"
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  {window.W_L.click_here_to_get_apikey}
                </Link>
              </div>
              <div>
                <Button loading={disabled} style={{ marginRight: "10px" }}
                  onClick={() => form.submit()}>{window.W_L.connect_test}</Button>
                <Button loading={disabled} htmlType="submit" type="primary">{window.W_L.apply}</Button>
              </div>
            </div>
          </Form.Item>
        </Form>
      </div>
    </React.Fragment>
  );
};

export default SettingsOpenKey;

const SettingsOpenKeyPage = wrapSettingsTab(
  "Settings.OpenKey",
  {
    title: "API Key",
    path: "settings/OpenKey",
    order: 9,
  },
  SettingsOpenKey
);

routes.register(
  "Settings.OpenKey",
  routeWithUserSession({
    path: "/settings/OpenKey",
    title: "API Key",
    render: pageProps => <SettingsOpenKeyPage {...pageProps} />,
  })
);