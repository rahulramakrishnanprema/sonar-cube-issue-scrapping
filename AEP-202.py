# Issue: AEP-202
# Generated: 2025-09-20T06:36:38.345622
# Thread: 8067122d
# Enhanced: LangChain structured generation
# AI Model: deepseek/deepseek-chat-v3.1:free
# Max Length: 25000 characters

package com.aep.api;

import com.aep.model.AepEntity;
import com.aep.service.AepService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import javax.persistence.criteria.Predicate;
import javax.validation.Valid;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

@RestController
@RequestMapping("/api/v1/aep-entities")
public class AepController {

    private static final Logger logger = LoggerFactory.getLogger(AepController.class);
    
    private final AepService aepService;

    @Autowired
    public AepController(AepService aepService) {
        this.aepService = aepService;
    }

    @PostMapping
    public ResponseEntity<AepEntity> createAepEntity(@Valid @RequestBody AepEntity aepEntity) {
        try {
            logger.info("Creating new AEP entity: {}", aepEntity);
            AepEntity savedEntity = aepService.save(aepEntity);
            logger.info("Successfully created AEP entity with ID: {}", savedEntity.getId());
            return ResponseEntity.status(HttpStatus.CREATED).body(savedEntity);
        } catch (Exception e) {
            logger.error("Error creating AEP entity: {}", e.getMessage(), e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }

    @GetMapping("/{id}")
    public ResponseEntity<AepEntity> getAepEntityById(@PathVariable Long id) {
        try {
            logger.debug("Fetching AEP entity with ID: {}", id);
            Optional<AepEntity> aepEntity = aepService.findById(id);
            
            if (aepEntity.isPresent()) {
                logger.debug("Successfully found AEP entity with ID: {}", id);
                return ResponseEntity.ok(aepEntity.get());
            } else {
                logger.warn("AEP entity with ID {} not found", id);
                return ResponseEntity.status(HttpStatus.NOT_FOUND).build();
            }
        } catch (Exception e) {
            logger.error("Error fetching AEP entity with ID {}: {}", id, e.getMessage(), e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }

    @GetMapping
    public ResponseEntity<Page<AepEntity>> getAllAepEntities(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "10") int size,
            @RequestParam(defaultValue = "id") String sortBy,
            @RequestParam(defaultValue = "asc") String sortDirection,
            @RequestParam(required = false) String name,
            @RequestParam(required = false) String status) {
        
        try {
            logger.debug("Fetching AEP entities with page: {}, size: {}, sortBy: {}, sortDirection: {}, name: {}, status: {}",
                    page, size, sortBy, sortDirection, name, status);
            
            Sort sort = Sort.by(Sort.Direction.fromString(sortDirection), sortBy);
            Pageable pageable = PageRequest.of(page, size, sort);
            
            Specification<AepEntity> spec = (root, query, criteriaBuilder) -> {
                List<Predicate> predicates = new ArrayList<>();
                
                if (name != null && !name.isEmpty()) {
                    predicates.add(criteriaBuilder.like(criteriaBuilder.lower(root.get("name")), "%" + name.toLowerCase() + "%"));
                }
                
                if (status != null && !status.isEmpty()) {
                    predicates.add(criteriaBuilder.equal(root.get("status"), status));
                }
                
                return criteriaBuilder.and(predicates.toArray(new Predicate[0]));
            };
            
            Page<AepEntity> aepEntities = aepService.findAll(spec, pageable);
            logger.debug("Successfully fetched {} AEP entities", aepEntities.getNumberOfElements());
            
            return ResponseEntity.ok(aepEntities);
        } catch (Exception e) {
            logger.error("Error fetching AEP entities: {}", e.getMessage(), e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }

    @PutMapping("/{id}")
    public ResponseEntity<AepEntity> updateAepEntity(@PathVariable Long id, @Valid @RequestBody AepEntity aepEntity) {
        try {
            logger.info("Updating AEP entity with ID: {}", id);
            
            if (!aepService.existsById(id)) {
                logger.warn("AEP entity with ID {} not found for update", id);
                return ResponseEntity.status(HttpStatus.NOT_FOUND).build();
            }
            
            aepEntity.setId(id);
            AepEntity updatedEntity = aepService.save(aepEntity);
            logger.info("Successfully updated AEP entity with ID: {}", id);
            
            return ResponseEntity.ok(updatedEntity);
        } catch (Exception e) {
            logger.error("Error updating AEP entity with ID {}: {}", id, e.getMessage(), e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteAepEntity(@PathVariable Long id) {
        try {
            logger.info("Deleting AEP entity with ID: {}", id);
            
            if (!aepService.existsById(id)) {
                logger.warn("AEP entity with ID {} not found for deletion", id);
                return ResponseEntity.status(HttpStatus.NOT_FOUND).build();
            }
            
            aepService.deleteById(id);
            logger.info("Successfully deleted AEP entity with ID: {}", id);
            
            return ResponseEntity.noContent().build();
        } catch (Exception e) {
            logger.error("Error deleting AEP entity with ID {}: {}", id, e.getMessage(), e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }
}
```

```java
package com.aep.service;

import com.aep.model.AepEntity;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;

import java.util.Optional;

public interface AepService {
    AepEntity save(AepEntity aepEntity);
    Optional<AepEntity> findById(Long id);
    Page<AepEntity> findAll(Specification<AepEntity> spec, Pageable pageable);
    boolean existsById(Long id);
    void deleteById(Long id);
}
```

```java
package com.aep.service;

import com.aep.model.AepEntity;
import com.aep.repository.AepRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Optional;

@Service
@Transactional
public class AepServiceImpl implements AepService {

    private final AepRepository aepRepository;

    @Autowired
    public AepServiceImpl(AepRepository aepRepository) {
        this.aepRepository = aepRepository;
    }

    @Override
    public AepEntity save(AepEntity aepEntity) {
        return aepRepository.save(aepEntity);
    }

    @Override
    public Optional<AepEntity> findById(Long id) {
        return aepRepository.findById(id);
    }

    @Override
    public Page<AepEntity> findAll(Specification<AepEntity> spec, Pageable pageable) {
        return aepRepository.findAll(spec, pageable);
    }

    @Override
    public boolean existsById(Long id) {
        return aepRepository.existsById(id);
    }

    @Override
    public void deleteById(Long id) {
        aepRepository.deleteById(id);
    }
}
```

```java
package com.aep.repository;

import com.aep.model.AepEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.stereotype.Repository;

@Repository
public interface AepRepository extends JpaRepository<AepEntity, Long>, JpaSpecificationExecutor<AepEntity> {
}
```

```java
package com.aep.model;

import javax.persistence.*;
import javax.validation.constraints.NotBlank;
import javax.validation.constraints.Size;
import java.time.LocalDateTime;

@Entity
@Table(name = "aep_entities")
public class AepEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotBlank(message = "Name is required")
    @Size(max = 100, message = "Name must be less than 100 characters")
    @Column(nullable = false, length = 100)
    private String name;

    @Size(max = 500, message = "Description must be less than 500 characters")
    @Column(length = 500)
    private String description;

    @Column(nullable = false)
    private String status;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    @PrePersist
    protected void onCreate() {
        createdAt = LocalDateTime.now();
        updatedAt = LocalDateTime.now();
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = LocalDateTime.now();
    }

    // Getters and setters
    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }

    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(LocalDateTime updatedAt) {
        this.updatedAt = updatedAt;
    }
}
```

```java
package com.aep.exception;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

@ResponseStatus(HttpStatus.NOT_FOUND)
public class ResourceNotFoundException extends RuntimeException {
    public ResourceNotFoundException(String message) {
        super(message);
    }
}
```

```java
package com.aep.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class WebConfig {

    @Bean
    public WebMvcConfigurer corsConfigurer() {
        return new WebMvcConfigurer() {
            @Override
            public void addCorsMappings(CorsRegistry registry) {
                registry.addMapping("/api/**")
                        .allowedOrigins("http://localhost:3000", "https://production-domain.com")
                        .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                        .allowedHeaders("*")
                        .allowCredentials(true);
            }
        };
    }
}
```

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.org/apm/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.org/apm/POM/4.0.0 
         http://maven.org/apm/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    
    <groupId>com.aep</groupId>
    <artifactId>aep-api</artifactId>
    <version>1.0.0</version>
    
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>2.7.0</version>
        <relativePath/>
    </parent>
    
    <properties>
        <java.version>11</java.version>
    </properties>
    
    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        <dependency>
            <groupId>mysql</groupId>
            <artifactId>mysql-connector-java</artifactId>
            <scope>runtime</scope>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
    
    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
```

```yaml
# application.yml
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/aep_db
    username: aep_user
    password: secure_password
    driver-class-name: com.mysql.cj.jdbc.Driver
  jpa:
    hibernate:
      ddl-auto: update
    properties:
      hibernate:
        dialect: org.hibernate.dialect.MySQL5InnoDBDialect
        format_sql: true
    show-sql: true
  web:
    cors:
      allowed-origins: http://localhost:3000,https://production-domain.com
      allowed-methods: GET,POST,PUT,DELETE,OPTIONS
      allowed-headers: "*"
      allow-credentials: true

server:
  port: 8080

logging:
  level:
    com.aep: DEBUG