/*
 * COPYRIGHT 2015 SEAGATE LLC
 *
 * THIS DRAWING/DOCUMENT, ITS SPECIFICATIONS, AND THE DATA CONTAINED
 * HEREIN, ARE THE EXCLUSIVE PROPERTY OF SEAGATE TECHNOLOGY
 * LIMITED, ISSUED IN STRICT CONFIDENCE AND SHALL NOT, WITHOUT
 * THE PRIOR WRITTEN PERMISSION OF SEAGATE TECHNOLOGY LIMITED,
 * BE REPRODUCED, COPIED, OR DISCLOSED TO A THIRD PARTY, OR
 * USED FOR ANY PURPOSE WHATSOEVER, OR STORED IN A RETRIEVAL SYSTEM
 * EXCEPT AS ALLOWED BY THE TERMS OF SEAGATE LICENSES AND AGREEMENTS.
 *
 * YOU SHOULD HAVE RECEIVED A COPY OF SEAGATE'S LICENSE ALONG WITH
 * THIS RELEASE. IF NOT PLEASE CONTACT A SEAGATE REPRESENTATIVE
 * http://www.seagate.com/contact
 *
 * Original author:  Arjun Hariharan <arjun.hariharan@seagate.com>
 * Original creation date: 17-Sep-2014
 */
package com.seagates3.authserver;

import com.seagates3.dao.DAODispatcher;
import com.seagates3.exception.ServerInitialisationException;
import com.seagates3.perf.S3Perf;
import io.netty.bootstrap.ServerBootstrap;
import io.netty.channel.Channel;
import io.netty.channel.ChannelOption;
import io.netty.channel.EventLoopGroup;
import io.netty.channel.nio.NioEventLoopGroup;
import io.netty.channel.socket.nio.NioServerSocketChannel;
import io.netty.handler.logging.LogLevel;
import io.netty.handler.logging.LoggingHandler;
import io.netty.util.concurrent.DefaultEventExecutorGroup;
import io.netty.util.concurrent.EventExecutorGroup;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Properties;
import org.apache.logging.log4j.Level;
import org.apache.logging.log4j.core.config.ConfigurationSource;
import org.apache.logging.log4j.core.config.Configurator;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class AuthServer {

    private static EventLoopGroup bossGroup, workerGroup;
    private static EventExecutorGroup executorGroup;

    private static Logger logger;

    private static void attachShutDownHook() {
        Runtime.getRuntime().addShutdownHook(new Thread() {
            @Override
            public void run() {
                S3Perf.clean();
                shutdownExecutors();
            }
        });
    }

    private static void shutdownExecutors() {
        bossGroup.shutdownGracefully();
        logger.info("Boss group shutdown");

        workerGroup.shutdownGracefully();
        logger.info("Worker group shutdown");

        executorGroup.shutdownGracefully();
        logger.info("Executor group shutdown");
    }

    /**
     * Read the properties file.
     */
    static void readConfig() throws FileNotFoundException, IOException {
        Path authProperties = Paths.get("", "resources", "authserver.properties");
        Properties authServerConfig = new Properties();
        InputStream input = new FileInputStream(authProperties.toString());
        authServerConfig.load(input);

        AuthServerConfig.init(authServerConfig);
    }

    /**
     * Create a File handler for Logger. Set level to ALL.
     */
    static void logInit() throws IOException, ServerInitialisationException {
        String logConfigFilePath = AuthServerConfig.getLogConfigFile();

        /**
         * If log4j config file is given, override the default Logging
         * properties file.
         */
        if (logConfigFilePath != null) {
            File logConfigFile = new File(AuthServerConfig.getLogConfigFile());
            if (logConfigFile.exists()) {
                ConfigurationSource source = new ConfigurationSource(
                        new FileInputStream(logConfigFile));
                Configurator.initialize(null, source);
            } else {
                throw new ServerInitialisationException(
                        "Logging config file doesn't exist.");
            }
        }

        String logLevel = AuthServerConfig.getLogLevel();
        if (logLevel != null) {
            Level level = Level.getLevel(logLevel);
            if (level == null) {
                throw new ServerInitialisationException(
                        "Incorrect logging level.");
            } else {
                Configurator.setRootLevel(level);
            }
        }
    }

    public static void main(String[] args) throws InterruptedException,
            IOException, ServerInitialisationException {
        readConfig();
        logInit();

        logger = LoggerFactory.getLogger(AuthServer.class.getName());

        SSLContextProvider.init();
        DAODispatcher.init();
        S3Perf.init();

        AuthServer.attachShutDownHook();

        // Configure the server.
        bossGroup = new NioEventLoopGroup(
                AuthServerConfig.getBossGroupThreads());
        logger.info("Created boss event loop group with "
                + AuthServerConfig.getBossGroupThreads() + " threads");

        workerGroup = new NioEventLoopGroup(
                AuthServerConfig.getWorkerGroupThreads());
        logger.info("Created worker event loop group with "
                + AuthServerConfig.getWorkerGroupThreads() + " threads");

        executorGroup = new DefaultEventExecutorGroup(
                AuthServerConfig.getEventExecutorThreads());
        logger.info("Created event executor with "
                + AuthServerConfig.getEventExecutorThreads() + " threads");

        ArrayList<Channel> serverChannels = new ArrayList<>();
        int httpPort = AuthServerConfig.getHttpPort();
        Channel serverChannel = httpServerBootstrap(bossGroup, workerGroup,
                executorGroup, httpPort
        );
        serverChannels.add(serverChannel);
        logger.info("Auth server is listening on port " + httpPort);

        if (AuthServerConfig.isHttpsEnabled()) {
            int httpsPort = AuthServerConfig.getHttpsPort();
            serverChannel = httpsServerBootstrap(bossGroup, workerGroup,
                    executorGroup, httpsPort
            );
            serverChannels.add(serverChannel);
            logger.info("Auth server is listening on port " + httpsPort);
        }

        for (Channel ch : serverChannels) {
            ch.closeFuture().sync();
        }

    }

    /**
     * Create a new ServerBootstrap for HTTP protocol.
     *
     * @param port HTTP port.
     */
    private static Channel httpServerBootstrap(EventLoopGroup bossGroup,
            EventLoopGroup workerGroup, EventExecutorGroup executorGroup,
            int port) throws InterruptedException {
        ServerBootstrap b = new ServerBootstrap();
        b.option(ChannelOption.SO_BACKLOG, 1024);
        b.group(bossGroup, workerGroup)
                .channel(NioServerSocketChannel.class)
                .handler(new LoggingHandler(LogLevel.INFO))
                .childHandler(new AuthServerHTTPInitializer(executorGroup));

        Channel serverChannel = b.bind(port).sync().channel();
        return serverChannel;
    }

    private static Channel httpsServerBootstrap(EventLoopGroup bossGroup,
            EventLoopGroup workerGroup, EventExecutorGroup executorGroup,
            int port) throws InterruptedException {
        ServerBootstrap b = new ServerBootstrap();
        b.option(ChannelOption.SO_BACKLOG, 1024);
        b.group(bossGroup, workerGroup)
                .channel(NioServerSocketChannel.class)
                .handler(new LoggingHandler(LogLevel.INFO))
                .childHandler(new AuthServerHTTPSInitializer(executorGroup));

        Channel serverChannel = b.bind(port).sync().channel();
        return serverChannel;
    }
}
